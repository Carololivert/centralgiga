import os
import re
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

TZ_BR = ZoneInfo("America/Sao_Paulo")
from bs4 import BeautifulSoup
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from urllib3.exceptions import InsecureRequestWarning

load_dotenv()


def ssl_verify_enabled() -> bool:
    return os.getenv("SGP_VERIFY_SSL", "true").strip().lower() not in {"0", "false", "no", "off"}


if not ssl_verify_enabled():
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

BASE_URL = "https://giganetwireless.sgp.net.br"
LOGIN_URL = f"{BASE_URL}/accounts/login"
REPORT_URL = f"{BASE_URL}/admin/atendimento/relatorios/ocorrencia/os/"

# =========================
# 1) LOGIN (SGP)
# =========================
def login_sgp(session: requests.Session) -> None:
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Referer": LOGIN_URL,
    })

    username = os.getenv("SGP_USER")
    password = os.getenv("SGP_PASS")
    if not username or not password:
        raise Exception("Variáveis SGP_USER / SGP_PASS não definidas.")

    verify_ssl = ssl_verify_enabled()

    r = session.get(LOGIN_URL, timeout=30, verify=verify_ssl)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    token_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    csrf = token_input["value"] if token_input else None

    payload = {"username": username, "password": password}
    if csrf:
        payload["csrfmiddlewaretoken"] = csrf

    r2 = session.post(LOGIN_URL, data=payload, allow_redirects=True, timeout=30, verify=verify_ssl)
    r2.raise_for_status()

    # Checagem simples de login (opcional, mas ajuda muito a debugar)
    if "accounts/login" in str(r2.url):
        raise Exception("Login parece não ter sido efetuado (a URL voltou pro login).")

# =========================
# 2) PARAMS: AGENDADAS (amanhã)
#    -> use LISTA de tuplas para suportar params repetidos (tipo_ocorrencia etc)
# =========================
def build_params_agendadas(day: datetime) -> List[Tuple[str, str]]:
    d = day.strftime("%d/%m/%Y")

    # Esses tipo_ocorrencia vieram do seu cURL e parecem ser os usados no relatório de OS
    tipo_ocorrencias = ["40", "39", "14", "49"]

    params: List[Tuple[str, str]] = [
        ("paginate_by", ""),  # se vazio, mantém padrão
        ("contrato_id", ""),
        ("numero_ocorrencia", ""),
        ("os_id", ""),
        ("tipoos", ""),
        ("prioridade", ""),
        ("empresa", ""),
        ("planos", ""),
        ("com_responsavel", ""),
        ("usuario", ""),
        ("usuario_finaliza", ""),
        ("usuario_oc", ""),
        ("veiculo", ""),
        ("data_cadastro_inicial", ""),
        ("data_cadastro_final", ""),
        ("com_agendamento", ""),  # pode deixar vazio; o filtro real está pela data
        ("com_comentario", ""),
        ("data_agendamento_inicial", f"{d} 00:00:00"),
        ("data_agendamento_final", f"{d} 23:59:59"),
        ("data_previsao_finalizacao_inicial", ""),
        ("data_previsao_finalizacao_final", ""),
        ("data_finalizacao_inicial", ""),
        ("data_finalizacao_final", ""),
        ("data_contrato_inicial", ""),
        ("data_contrato_final", ""),
        ("retorno_dias", ""),
        ("tasksyncfilter", ""),
        ("relacionamento_itens_marcados_checklist", "and"),
        ("itens_marcados_checklist-autocomplete", ""),
        ("relacionamento_itens_desmarcados_checklist", "and"),
        ("itens_desmarcados_checklist-autocomplete", ""),
        ("data_checklist_marcado_inicio", ""),
        ("data_checklist_marcado_final", ""),
        ("conclusao_checklist_op", ""),
        ("conclusao_checklist", ""),
        ("page", ""),
        ("printpdf", ""),
        ("printexcel", ""),
    ]

    for t in tipo_ocorrencias:
        params.append(("tipo_ocorrencia", t))

    # colunas omitidas (apareciam repetidas no seu link)
    params.append(("omitir_colunas", "conclusao_checklist"))
    params.append(("omitir_colunas", "servicoprestado"))

    return params

# =========================
# 3) LISTA: PEGAR LINHAS E LINK DA OS
# =========================
def _make_unique_headers(th_texts: List[str]) -> List[str]:
    """
    DataTables costuma ter colunas vazias (checkbox/ações).
    Aqui garantimos headers únicos e utilizáveis.
    """
    out: List[str] = []
    seen: Dict[str, int] = {}
    for i, h in enumerate(th_texts):
        h = (h or "").strip()
        if not h:
            h = f"col_{i}"
        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 0
        out.append(h)
    return out

def _extract_os_href_from_row(tr: Any) -> Optional[str]:
    """
    Pega o link da OS de forma robusta.
    Prioriza links que pareçam levar ao detalhe da OS.
    """
    # 1) procura links típicos de detalhe de OS no admin
    candidates = tr.select("a[href]")
    for a in candidates:
        href = a.get("href") or ""
        href_low = href.lower()
        if "/admin/atendimento/" in href_low and ("/os/" in href_low or "ordemservico" in href_low):
            return href
    # 2) fallback: o primeiro link que tenha um número no caminho (id)
    for a in candidates:
        href = a.get("href") or ""
        if re.search(r"/\d+/", href):
            return href
    return None

def parse_rows_with_id_link(html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#DataTables_Table_0") or soup.select_one("table")
    if not table:
        raise Exception("Não achei a tabela na página do relatório (ajustar seletor).")

    raw_headers = [th.get_text(" ", strip=True) for th in table.select("thead th")]
    headers = _make_unique_headers(raw_headers)

    rows: List[Dict[str, str]] = []
    for tr in table.select("tbody tr"):
        tds = tr.select("td")
        if not tds:
            continue

        values = [td.get_text(" ", strip=True) for td in tds]

        row: Dict[str, str] = {}
        for i, v in enumerate(values):
            key = headers[i] if i < len(headers) else f"col_{i}"
            row[key] = v

        # link da OS (robusto)
        row["_id_href"] = _extract_os_href_from_row(tr)
        rows.append(row)

    return rows

# =========================
# 4) EXTRAÇÕES NA OS
# =========================
def extract_nome_razao(soup: BeautifulSoup) -> Optional[str]:
    text = soup.get_text("\n", strip=True)
    m = re.search(r"Nome/Raz[aã]o Social:\s*(.+)", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).split("\n")[0].strip()
    return None

def extract_aberta_por(soup: BeautifulSoup) -> Optional[str]:
    text = soup.get_text("\n", strip=True)
    m = re.search(r"Aberta\s*Por\s*:\s*(.+)", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).split("\n")[0].strip()
    return None

def extract_problema_reportado(soup: BeautifulSoup) -> str:
    # tenta achar label "Problema Reportado" e o textarea próximo
    tag = soup.find(string=re.compile(r"Problema\s*Reportado", re.IGNORECASE))
    if tag:
        container = tag.parent
        for _ in range(8):
            if not container:
                break
            ta = container.select_one("textarea")
            if ta:
                return (ta.get_text("\n", strip=True) or "").strip()
            container = container.parent

    # fallback: qualquer textarea que contenha "termo"
    for ta in soup.select("textarea"):
        val = (ta.get_text("\n", strip=True) or "").strip()
        if re.search(r"\btermo\b", val, flags=re.IGNORECASE):
            return val

    return ""

def termo_ok(problema: str) -> bool:
    p = (problema or "").lower()

    # aceita (x) sim / ( x ) sim / (X) SIM
    if re.search(r"\(\s*x\s*\)\s*sim\b", p):
        return True

    # aceita termo físico com variações
    if re.search(r"\(\s*x\s*\)\s*entregar\s+termo", p):
        return True

    return False

# =========================
# 5) RELATÓRIO FINAL
# =========================
def _find_key_like(row: Dict[str, str], wanted: str) -> Optional[str]:
    """
    Ajuda a encontrar colunas mesmo se o header vier levemente diferente.
    """
    wanted_low = wanted.lower()
    for k in row.keys():
        if k.lower() == wanted_low:
            return k
    for k in row.keys():
        if wanted_low in k.lower():
            return k
    return None

def gerar_relatorio_instalacoes_agendadas(session: requests.Session, day: datetime) -> str:
    params = build_params_agendadas(day)

    r = session.get(REPORT_URL, params=params, timeout=30, verify=ssl_verify_enabled())
    r.raise_for_status()

    rows = parse_rows_with_id_link(r.text)

    # tenta achar nomes de colunas (robusto)
    sample = rows[0] if rows else {}
    key_status = _find_key_like(sample, "Status") or "Status"
    key_motivo = _find_key_like(sample, "Motivo") or "Motivo"

    instalacoes_hrefs: List[str] = []
    for row in rows:
        status = (row.get(key_status) or "").strip().lower()
        motivo = (row.get(key_motivo) or "").strip().lower()

        # status pode vir "Aberta Offline" etc
        if "aberta" not in status:
            continue

        # motivo pode vir com texto extra
        if "instalação de kit" not in motivo and "instalacao de kit" not in motivo:
            continue

        href = row.get("_id_href")
        if not href:
            continue

        instalacoes_hrefs.append(href)

    print("Total de instalações encontradas:", len(instalacoes_hrefs))
    for h in instalacoes_hrefs[:10]:
        print("OS:", h)

    problemas: List[str] = []
    for href in instalacoes_hrefs:
        url = urljoin(BASE_URL, href)
        rr = session.get(url, timeout=30, verify=ssl_verify_enabled())
        rr.raise_for_status()

        soup = BeautifulSoup(rr.text, "html.parser")
        nome = extract_nome_razao(soup) or "CLIENTE (não achei o nome)"
        aberta_por = extract_aberta_por(soup) or "desconhecido"
        problema = extract_problema_reportado(soup)

        if not termo_ok(problema):
            problemas.append(f"{nome} (Sem informação na OS) / {aberta_por}")

    ddmmaa = day.strftime("%d/%m/%y")
    if problemas:
        return (
            f"Instalações agendadas (status termo manual / eletrônico) {ddmmaa}: PENDENTE\n\n"
            + "\n".join(problemas)
        )
    else:
        return f"Instalações agendadas (status termo manual / eletrônico) {ddmmaa}: OK"

def main():
    session = requests.Session()
    login_sgp(session)

    amanha = datetime.now(TZ_BR).replace(tzinfo=None) + timedelta(days=1)
    print(gerar_relatorio_instalacoes_agendadas(session, amanha))

if __name__ == "__main__":
    main()
