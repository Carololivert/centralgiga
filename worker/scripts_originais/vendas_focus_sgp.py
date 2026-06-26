#!/usr/bin/env python3
"""
vendas_focus_sgp.py

Fluxo COMPLETO num comando só (junta o relatorio_nao_cadastrados.py + checar_sgp.py):

  1) Loga no FocusChat, varre o Histórico de Atendimentos (setores de VENDAS) e
     coleta NOME + NÚMERO + DATA de cada atendimento.  (Playwright)
  2) Salva a lista bruta em vendas_do_dia.csv (backup).
  3) Consulta cada número no SGP e gera o relatório FINAL só com quem
     NÃO tem cadastro (não virou cliente).  (requests)

Uso:
    python vendas_focus_sgp.py                 # data de hoje
    python vendas_focus_sgp.py 03/06/2026      # uma data específica
    python vendas_focus_sgp.py todas           # não filtra por data (pega tudo)

Dependências:
    pip install playwright requests beautifulsoup4 python-dotenv
    python -m playwright install chromium

Credenciais (no .env da mesma pasta):
    FOCUS_USER=grupomomento2@giganetdf.com
    FOCUS_PASS=sua_senha_focus
    SGP_USER=seu_usuario_sgp
    SGP_PASS=sua_senha_sgp
    # opcional: SGP_VERIFY_SSL=false   (se der erro de certificado)
"""

import os
import re
import sys
import csv
import time
import unicodedata
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib3.exceptions import InsecureRequestWarning
from playwright.sync_api import sync_playwright

load_dotenv()

# ============================================================
# CONFIGURAÇÃO
# ============================================================
FOCUS_LOGIN_URL    = "https://app.focuschat.com.br/login"
FOCUS_HISTORIC_URL = "https://app.focuschat.com.br/historic"
FOCUS_USER = os.getenv("FOCUS_USER")
FOCUS_PASS = os.getenv("FOCUS_PASS")

MARCADORES_ASSINOU = [
    "termo de adesao referente ao seu contrato numero",
    "seja bem-vindo a familia giganet",
    "setor de cadastro",
]

APLICAR_FILTRO = True
HEADLESS = False
MAX_ITENS = 40
ARQUIVO_VENDAS = "vendas_do_dia.csv"     # backup da lista bruta de VENDAS
SAIDA_FINAL    = "relatorio_final.csv"   # relatório final (não-clientes)

# SGP
BASE = "https://giganetwireless.sgp.net.br"
LOGIN_URL = f"{BASE}/accounts/login"
AUTOCOMPLETE_URL = f"{BASE}/public/autocomplete/ClienteAutocomplete/"


def ssl_verify_enabled() -> bool:
    return os.getenv("SGP_VERIFY_SSL", "true").strip().lower() not in {"0", "false", "no", "off"}


if not ssl_verify_enabled():
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


# ============================================================
# UTILIDADES (FocusChat)
# ============================================================
def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(t.lower().split())

def assinou(texto_conversa: str) -> bool:
    norm = normalizar(texto_conversa)
    return any(m in norm for m in MARCADORES_ASSINOU)

def limpar_nome(nome: str) -> str:
    return re.sub(r"[^\w\s\.\-']", "", nome, flags=re.UNICODE).strip()


# ============================================================
# PLAYWRIGHT (FocusChat)
# ============================================================
def fazer_login(page):
    page.goto(FOCUS_LOGIN_URL)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    inputs = page.locator("form input")
    inputs.nth(0).fill(FOCUS_USER)
    page.locator("input[type='password']").fill(FOCUS_PASS)
    page.locator("button[type='submit']").click()
    page.wait_for_timeout(4000)
    print(f"[debug] depois do login, URL = {page.url}")
    page.screenshot(path="debug_apos_login.png", full_page=True)

def fechar_popups(page):
    try:
        page.evaluate("""() => {
            document.querySelectorAll(
                '#onesignal-slidedown-container, .onesignal-slidedown-container, #onesignal-bell-container'
            ).forEach(el => el.remove());
        }""")
    except Exception:
        pass

def selecionar_setores(page, setores):
    fechar_popups(page)
    page.get_by_role("button", name="filtros").first.click()
    page.wait_for_timeout(1000)
    page.get_by_role("button", name=re.compile(r"^\s*setor\s*$", re.I)).first.click()
    page.wait_for_timeout(800)
    campo = page.locator("input.MuiAutocomplete-input").first
    for setor in setores:
        campo.click()
        campo.fill("")
        campo.type(setor, delay=60)
        page.wait_for_timeout(900)
        opcao = page.get_by_role("option", name=setor, exact=True)
        if opcao.count() == 0:
            opcao = page.get_by_role("option").filter(has_text=setor)
        opcao.first.click()
        page.wait_for_timeout(500)
        print(f"[debug] setor selecionado: {setor}")
    fechar_popups(page)
    page.locator("button[aria-label='filtrar']").click()
    page.wait_for_timeout(2000)

def abrir_historico(page):
    page.goto(FOCUS_HISTORIC_URL)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    page.wait_for_timeout(3000)
    print(f"[debug] no historico, URL = {page.url} | titulo = {page.title()}")
    fechar_popups(page)
    if APLICAR_FILTRO:
        selecionar_setores(page, ["VENDAS PLANTÃO", "VENDAS"])
    page.screenshot(path="debug_historico.png", full_page=True)
    qtd = page.locator(".item.contact").count()
    print(f"[debug] itens '.item.contact' encontrados: {qtd}")
    try:
        page.wait_for_selector(".item.contact", timeout=20000)
    except Exception:
        page.screenshot(path="debug_lista_vazia.png", full_page=True)
        raise

def achar_container_scroll(page):
    return page.evaluate_handle("""() => {
        const el = document.querySelector('.item.contact');
        if (!el) return null;
        let p = el.parentElement;
        while (p) {
            const s = getComputedStyle(p);
            if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && p.scrollHeight > p.clientHeight)
                return p;
            p = p.parentElement;
        }
        return null;
    }""")

def total_estimado(page, container):
    return page.evaluate("""(c) => {
        const inner = c.querySelector('div[style*="height"]') || c.firstElementChild;
        const h = inner ? inner.offsetHeight : c.scrollHeight;
        return Math.max(1, Math.round(h / 85));
    }""", container)

def linhas_renderizadas(page):
    return page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('.item.contact').forEach(c => {
            const row = c.closest('[style*="position: absolute"]') || c.parentElement;
            const top = row ? parseInt(row.style.top || '0', 10) : 0;
            const idx = Math.round(top / 85);
            const t = row ? row.querySelector('.item.time') : null;
            out.push({ idx, name: c.innerText.trim(), time: t ? t.innerText.trim() : '' });
        });
        return out;
    }""")

def clicar_item(page, idx) -> bool:
    return page.evaluate("""(idx) => {
        for (const c of document.querySelectorAll('.item.contact')) {
            const row = c.closest('[style*="position: absolute"]') || c.parentElement;
            const top = row ? parseInt(row.style.top || '0', 10) : 0;
            if (Math.round(top / 85) === idx) { (row || c).click(); return true; }
        }
        return false;
    }""", idx)

def rolar(page, container, delta):
    page.evaluate("""([c, d]) => { c.scrollTop += d; }""", [container, delta])

def no_fim(page, container) -> bool:
    return page.evaluate("""(c) => (c.scrollTop + c.clientHeight) >= (c.scrollHeight - 5)""", container)

def clicar_nome(page, nome="") -> bool:
    return page.evaluate("""(want) => {
        const fold = s => (s || '').toLowerCase().normalize('NFD')
                          .replace(/[\\u0300-\\u036f]/g, '').replace(/[^a-z0-9]/g, '');
        const w = fold(want).slice(0, 10);
        if (!w) return false;
        for (const el of document.querySelectorAll('[role="button"]')) {
            if (el.closest('[style*="position: absolute"]')) continue;
            if (fold(el.innerText || '').includes(w)) { el.click(); return true; }
        }
        return false;
    }""", nome)

def ler_detalhes(page, nome_esperado="") -> dict:
    rx_num = r"\+?55\s*\(?\d{2}\)?[\s-]*\d{4,5}-?\d{4}"
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
    except Exception:
        pass

    data = ""
    try:
        m = re.search(r"\d{2}/\d{2}/\d{4}", page.locator("body").inner_text())
        if m:
            data = m.group(0)
    except Exception:
        pass

    numero = ""
    page.wait_for_timeout(1200)
    for tentativa in range(2):
        if not clicar_nome(page, nome_esperado):
            page.wait_for_timeout(400)
            continue
        for _ in range(12):
            try:
                heads = page.get_by_role("heading").all_inner_texts()
            except Exception:
                heads = []
            for h in heads:
                mm = re.search(rx_num, h)
                if mm:
                    numero = mm.group(0).strip()
                    break
            if numero:
                break
            page.wait_for_timeout(300)
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(250)
        except Exception:
            pass
        if numero:
            break

    return {"numero": numero, "data": data}


def _data_obj(s):
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except Exception:
        return None


def coletar_vendas(filtro_data):
    """Coleta os atendimentos do FocusChat e devolve lista de dicts {nome, numero, data}.
    Também salva o backup em ARQUIVO_VENDAS."""
    if not FOCUS_USER or not FOCUS_PASS:
        raise SystemExit("Defina FOCUS_USER e FOCUS_PASS no .env")

    resultados = {}
    alvo = _data_obj(filtro_data) if filtro_data else None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        try:
            fazer_login(page)
            abrir_historico(page)

            container = achar_container_scroll(page)
            total = total_estimado(page, container)
            print(f"~{total} atendimentos na lista filtrada.")

            processados = set()
            sem_progresso = 0
            while len(processados) < MAX_ITENS and sem_progresso < 5:
                linhas = linhas_renderizadas(page)
                pendentes = [l for l in linhas if l["idx"] not in processados]
                if not pendentes:
                    if no_fim(page, container):
                        break
                    rolar(page, container, 400)
                    page.wait_for_timeout(500)
                    sem_progresso += 1
                    continue
                sem_progresso = 0
                for l in sorted(pendentes, key=lambda x: x["idx"]):
                    idx = l["idx"]
                    try:
                        if not clicar_item(page, idx):
                            processados.add(idx)
                            continue
                        det = ler_detalhes(page, l["name"])
                        nome = limpar_nome(l["name"])
                        d_item = _data_obj(det["data"])
                        if (alvo is None) or (d_item == alvo) or (d_item is None):
                            chave = det["numero"] or nome
                            resultados[chave] = {
                                "nome": nome,
                                "numero": det["numero"],
                                "data": det["data"] or l["time"],
                            }
                            print(f"  [{len(resultados)}] {nome} | {det['numero']} | {det['data']}")
                    except Exception as e:
                        print(f"  (erro no item {idx}: {e})")
                    finally:
                        processados.add(idx)
                rolar(page, container, 400)
                page.wait_for_timeout(500)
        finally:
            browser.close()

    linhas = list(resultados.values())
    with open(ARQUIVO_VENDAS, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["nome", "numero", "data"])
        w.writeheader()
        for linha in linhas:
            w.writerow(linha)
    print(f"\nLista de VENDAS salva em {ARQUIVO_VENDAS} - {len(linhas)} atendimento(s).")
    return linhas


# ============================================================
# SGP (checagem)
# ============================================================
def login_sgp(session: requests.Session) -> None:
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": LOGIN_URL})
    username = os.getenv("SGP_USER")
    password = os.getenv("SGP_PASS")
    if not username or not password:
        raise Exception("Defina SGP_USER e SGP_PASS no arquivo .env")
    verify_ssl = ssl_verify_enabled()
    res = session.get(LOGIN_URL, verify=verify_ssl)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    token_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    csrf = token_input["value"] if token_input else None
    payload = {"username": username, "password": password}
    if csrf:
        payload["csrfmiddlewaretoken"] = csrf
    login_res = session.post(LOGIN_URL, data=payload, allow_redirects=True, verify=verify_ssl)
    login_res.raise_for_status()


def _so_digitos(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


def variacoes_telefone(telefone: str) -> list:
    d = _so_digitos(telefone)
    if d.startswith("55") and len(d) >= 12:
        d = d[2:]
    if len(d) < 10:
        return [telefone.strip()]
    ddd = d[:2]
    resto = d[2:]
    formas_resto = {resto}
    if len(resto) == 8:
        formas_resto.add("9" + resto)
    elif len(resto) == 9 and resto.startswith("9"):
        formas_resto.add(resto[1:])
    out = []
    for r in formas_resto:
        if len(r) == 9:
            out.append(f"({ddd}) {r[:5]}-{r[5:]}")
        elif len(r) == 8:
            out.append(f"({ddd}) {r[:4]}-{r[4:]}")
        out.append(f"{ddd}{r}")
    return out


def cliente_existe(session: requests.Session, telefone: str) -> bool:
    for termo in variacoes_telefone(telefone):
        r = session.get(
            AUTOCOMPLETE_URL,
            params={"tconsulta": "", "term": termo},
            verify=ssl_verify_enabled(),
            timeout=30,
        )
        r.raise_for_status()
        try:
            dados = r.json()
        except ValueError:
            continue
        if isinstance(dados, dict):
            dados = dados.get("results") or dados.get("data") or []
        if dados:
            return True
    return False


def checar_no_sgp(linhas):
    """Recebe a lista de vendas e devolve só quem NÃO é cliente."""
    print(f"\n{len(linhas)} contato(s) para conferir no SGP...")
    session = requests.Session()
    login_sgp(session)

    nao_clientes = []
    for i, linha in enumerate(linhas, 1):
        nome = (linha.get("nome") or "").strip()
        numero = (linha.get("numero") or "").strip()

        if not numero:
            linha["status_sgp"] = "SEM NUMERO"
            nao_clientes.append(linha)
            print(f"  [{i}/{len(linhas)}] {nome}: sem numero (revisar)")
            continue
        try:
            ja_cliente = cliente_existe(session, numero)
        except Exception as e:
            linha["status_sgp"] = f"ERRO: {e}"
            nao_clientes.append(linha)
            print(f"  [{i}/{len(linhas)}] {nome} {numero}: erro na consulta ({e})")
            continue

        if ja_cliente:
            print(f"  [{i}/{len(linhas)}] {nome} {numero}: JA E CLIENTE (fora)")
        else:
            linha["status_sgp"] = "NAO CADASTRADO"
            nao_clientes.append(linha)
            print(f"  [{i}/{len(linhas)}] {nome} {numero}: nao cadastrado (ENTRA)")
        time.sleep(0.3)
    return nao_clientes


# ============================================================
# MAIN
# ============================================================
def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg is None:
        filtro = date.today().strftime("%d/%m/%Y")
    elif arg.lower() == "todas":
        filtro = None
    else:
        filtro = datetime.strptime(arg, "%d/%m/%Y").strftime("%d/%m/%Y")

    # 1) coleta no FocusChat
    vendas = coletar_vendas(filtro)
    if not vendas:
        print("Nenhum atendimento coletado. Encerrando.")
        return

    # 2) checa no SGP
    nao_clientes = checar_no_sgp(vendas)

    # 3) salva e imprime o relatório final
    campos = ["nome", "numero", "data", "status_sgp"]
    with open(SAIDA_FINAL, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for linha in nao_clientes:
            w.writerow({c: linha.get(c, "") for c in campos})

    print("\n" + "=" * 60)
    print("  RELATORIO - CLIENTES DE VENDAS QUE NAO CADASTRARAM")
    print("=" * 60)
    if not nao_clientes:
        print("  Nenhum! Todos os atendidos viraram clientes. :)")
    else:
        for i, linha in enumerate(nao_clientes, 1):
            nome = (linha.get("nome") or "(sem nome)").strip()
            numero = (linha.get("numero") or "(sem numero)").strip()
            data = (linha.get("data") or "").strip()
            obs = "  <-- conferir manualmente" if linha.get("status_sgp") == "SEM NUMERO" else ""
            print(f"  {i:>2}. {nome:<32} {numero:<20} {data}{obs}")
    print("=" * 60)
    print(f"  Total: {len(nao_clientes)} pessoa(s) que NAO sao clientes")
    print(f"  (backup das vendas em {ARQUIVO_VENDAS} | relatorio final em {SAIDA_FINAL})")
    print("=" * 60)


if __name__ == "__main__":
    main()