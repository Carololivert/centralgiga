#!/usr/bin/env python3
"""
remover_linhas.py

1) DESCOBRE (requests): roda o relatório de cancelados (Telefone fixo ilimitado)
   mês a mês e acha os serviços de telefonia que AINDA têm número.
2) REGISTRA cada número num CSV (numeros_removidos.csv) ANTES de qualquer ação.
3) REMOVE (Playwright): abre o serviço, vai na aba Linhas, clica Opções > Remover
   e aceita o popup "Deseja realmente excluir a Linha?".

>>> SEGURANÇA:
   - DRY_RUN = False  -> só SIMULA (mostra o que removeria, NÃO remove). Padrão.
   - Troque para False só depois de conferir a simulação.
   - HEADLESS = False -> você vê o navegador removendo (recomendado nas 1as vezes).
"""

import os
import re
import csv
import calendar
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib3.exceptions import InsecureRequestWarning
from playwright.sync_api import sync_playwright

load_dotenv()

SGP_BASE   = "https://giganetwireless.sgp.net.br"
LOGIN_URL  = f"{SGP_BASE}/accounts/login"
REPORT_URL = f"{SGP_BASE}/admin/relatorios/contrato/status/"

# ---- TRAVAS DE SEGURANÇA ---------------------------------------------------
DRY_RUN  = False     # True = só simula | False = remove de verdade
HEADLESS = False    # False = você vê o navegador

# ---- Período a varrer ------------------------------------------------------
ANO_INICIO, MES_INICIO = 2026, 1
ANO_FIM,    MES_FIM    = 2026, 6

LOG_CSV = "numeros_removidos.csv"


def ssl_verify_enabled() -> bool:
    return os.getenv("SGP_VERIFY_SSL", "true").strip().lower() not in {"0", "false", "no", "off"}


if not ssl_verify_enabled():
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


# ===========================================================================
# REGISTRO (sempre antes de remover)
# ===========================================================================
def registrar(numero, contrato, cliente, url, status):
    novo = not os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(["data_hora", "numero", "contrato", "cliente", "servico_url", "status"])
        w.writerow([datetime.now().strftime("%d/%m/%Y %H:%M:%S"), numero, contrato, cliente, url, status])


# ===========================================================================
# DESCOBERTA (requests) — reaproveita a lógica do relatório
# ===========================================================================
def login_sgp(session):
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": LOGIN_URL})
    v = ssl_verify_enabled()
    soup = BeautifulSoup(session.get(LOGIN_URL, verify=v).text, "html.parser")
    tok = soup.find("input", {"name": "csrfmiddlewaretoken"})
    payload = {"username": os.getenv("SGP_USER"), "password": os.getenv("SGP_PASS")}
    if tok:
        payload["csrfmiddlewaretoken"] = tok["value"]
    session.post(LOGIN_URL, data=payload, allow_redirects=True, verify=v).raise_for_status()


def obter_tokens(session):
    soup = BeautifulSoup(session.get(REPORT_URL, verify=ssl_verify_enabled()).text, "html.parser")
    return {n: soup.find("input", {"name": n})["value"]
            for n in ("csrfmiddlewaretoken", "dpb_token") if soup.find("input", {"name": n})}


def meses(ano_i, mes_i, ano_f, mes_f):
    y, m = ano_i, mes_i
    while (y, m) <= (ano_f, mes_f):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def build_params(ano, mes, tokens):
    return {
        "tipo_pesquisa": "0", "status": "3", "contrato": "5",
        "data_inicial": f"01/{mes:02d}/{ano}",
        "data_final": f"{calendar.monthrange(ano, mes)[1]:02d}/{mes:02d}/{ano}",
        "paginate_by": "1000", **tokens,
    }


def parse_contratos(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#DataTables_Table_0")
    if table is None:
        for t in soup.find_all("table"):
            if "Observa" in t.get_text():
                table = t
                break
    if table is None:
        return []
    out, vistos = [], set()
    for tr in (table.select("tbody tr") or table.select("tr")):
        a = tr.find("a", href=True)
        if not a:
            continue
        label = a.get_text(strip=True)
        url = urljoin(SGP_BASE, a["href"])
        if label and url not in vistos:
            vistos.add(url)
            out.append((label, url))
    return out


def extrair_servicos(html):
    """Da página do cliente, devolve (numero, servico_url) dos serviços de
    telefonia CANCELADOS que ainda têm número em 'Linhas:'."""
    soup = BeautifulSoup(html, "html.parser")
    achados = []
    for a in soup.find_all("a", href=True):
        if "/servicos/telefonia/" not in a["href"]:
            continue
        bloco = a.get_text(" ", strip=True)
        if "cancelad" not in bloco.lower():
            continue
        m = re.search(r"Linhas?\s*:\s*(.*?)\s*Situa", bloco, re.I)
        if not m:
            continue
        for chunk in re.split(r"[,;/]", m.group(1)):
            d = re.sub(r"\D", "", chunk)
            if 8 <= len(d) <= 13:
                achados.append((d, urljoin(SGP_BASE, a["href"])))
    return achados


def descobrir():
    s = requests.Session()
    print("Logando no SGP (descoberta)...")
    login_sgp(s)
    tokens = obter_tokens(s)

    servicos = {}  # servico_url -> (numero, contrato, cliente)
    for ano, mes in meses(ANO_INICIO, MES_INICIO, ANO_FIM, MES_FIM):
        rep = s.get(REPORT_URL, params=build_params(ano, mes, tokens), verify=ssl_verify_enabled())
        for label, client_url in parse_contratos(rep.text):
            html = s.get(client_url, verify=ssl_verify_enabled()).text
            for numero, surl in extrair_servicos(html):
                num_c, _, nome = label.partition(" - ")
                servicos.setdefault(surl, (numero, num_c.strip(), nome.strip()))
    return servicos


# ===========================================================================
# REMOÇÃO (Playwright)
# ===========================================================================
def login_playwright(page):
    page.goto(LOGIN_URL)
    page.fill("input[name='username']", os.getenv("SGP_USER"))
    page.fill("input[name='password']", os.getenv("SGP_PASS"))
    page.press("input[name='password']", "Enter")
    page.wait_for_load_state("load")


def linhas_da_tabela(page):
    """Retorna locators das linhas da tabela que contêm um número (MSISDN)."""
    return page.locator("table tr").filter(has_text=re.compile(r"\d{10,13}"))


def abrir_aba_linhas(page):
    for tentativa in (
        lambda: page.get_by_role("link", name="Linhas").first.click(timeout=3000),
        lambda: page.get_by_text("Linhas", exact=True).first.click(timeout=3000),
    ):
        try:
            tentativa()
            page.wait_for_timeout(700)
            return
        except Exception:
            continue


def processar(servicos):
    total_reg = total_rem = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=0 if HEADLESS else 250)
        page = browser.new_page()
        page.on("dialog", lambda d: d.accept())  # aceita "Deseja realmente excluir a Linha?"
        print("Logando no SGP (remoção)...")
        login_playwright(page)

        for url, (numero, contrato, cliente) in servicos.items():
            print(f"\nServiço {url}  (contrato {contrato} - {cliente})")
            page.goto(url)
            page.wait_for_load_state("load")
            abrir_aba_linhas(page)

            linhas = linhas_da_tabela(page)
            if linhas.count() == 0:
                print("   sem linha (já removida) — pulando")
                continue

            if DRY_RUN:
                for i in range(linhas.count()):
                    txt = linhas.nth(i).inner_text()
                    mm = re.search(r"\b(\d{10,13})\b", txt)
                    numr = mm.group(1) if mm else numero
                    registrar(numr, contrato, cliente, url, "SIMULADO")
                    total_reg += 1
                    print(f"   [SIMULADO] removeria a linha {numr}")
            else:
                # remove uma de cada vez e recarrega (a tabela muda a cada remoção)
                while True:
                    linhas = linhas_da_tabela(page)
                    if linhas.count() == 0:
                        break
                    row = linhas.first
                    txt = row.inner_text()
                    mm = re.search(r"\b(\d{10,13})\b", txt)
                    numr = mm.group(1) if mm else numero
                    registrar(numr, contrato, cliente, url, "REMOVIDO")  # registra ANTES
                    total_reg += 1
                    row.get_by_text("Opções").first.click()
                    page.get_by_text("Remover", exact=True).first.click()  # popup aceito automaticamente
                    page.wait_for_timeout(1500)
                    total_rem += 1
                    print(f"   [REMOVIDO] linha {numr}")
                    page.goto(url)
                    page.wait_for_load_state("load")
                    abrir_aba_linhas(page)

        browser.close()
    return total_reg, total_rem


# ===========================================================================
def main():
    servicos = descobrir()
    print(f"\n{len(servicos)} serviço(s) com número a liberar.\n" + "=" * 50)

    reg, rem = processar(servicos)

    print("\n" + "=" * 50)
    if DRY_RUN:
        print(f"SIMULAÇÃO: {reg} linha(s) seriam removidas.")
        print("Confira o numeros_removidos.csv. Quando estiver ok, troque DRY_RUN = False.")
    else:
        print(f"FEITO: {rem} linha(s) removidas. Registro em {LOG_CSV}")
    print("=" * 50)


if __name__ == "__main__":
    main()