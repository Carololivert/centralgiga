import os
import re
import requests
import unicodedata
from datetime import datetime
from bs4 import BeautifulSoup
from datetime import timedelta
from zoneinfo import ZoneInfo

TZ_BR = ZoneInfo("America/Sao_Paulo")


def agora_br() -> datetime:
    return datetime.now(TZ_BR).replace(tzinfo=None)
from dotenv import load_dotenv
from urllib3.exceptions import InsecureRequestWarning


load_dotenv()


def ssl_verify_enabled() -> bool:
    return os.getenv("SGP_VERIFY_SSL", "true").strip().lower() not in {"0", "false", "no", "off"}


if not ssl_verify_enabled():
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


# =========================
# 1) LOGIN (SGP)
# =========================
def login_sgp(session: requests.Session) -> None:
    login_url = "https://giganetwireless.sgp.net.br/accounts/login"

    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": login_url
    })

    username = os.getenv("SGP_USER")
    password = os.getenv("SGP_PASS")
    if not username or not password:
        raise Exception("Variáveis de ambiente SGP_USER ou SGP_PASS não definidas")

    verify_ssl = ssl_verify_enabled()

    res = session.get(login_url, verify=verify_ssl)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    token_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    csrf = token_input["value"] if token_input else None

    payload = {"username": username, "password": password}
    if csrf:
        payload["csrfmiddlewaretoken"] = csrf

    login_res = session.post(login_url, data=payload, allow_redirects=True, verify=verify_ssl)
    login_res.raise_for_status()


# =========================
# 2) RELATÓRIO: TABELA OS
# =========================
REPORT_URL = "https://giganetwireless.sgp.net.br/admin/atendimento/relatorios/ocorrencia/os/"

MOTIVOS_ESPECIAIS = {
    "Mudança Endereço - casa",
    "Mudança Endereço - apartamento Condomínios",
    "Instalação de KIT - apartamento Condomínios",
    "Mudança Endereço - apartamento/prédio geral",
    "Instalação de KIT - casa",
    "Instalação de KIT - apartamento/prédio geral",
    "Remoção de KIT",
    "Entrega de Carnê físico",
}

def build_params_for_day(day: datetime) -> dict:
    d = day.strftime("%d/%m/%Y")
    return {
        "status": "1",
        "paginate_by": "",
        "data_agendamento_inicial": f"{d} 00:00:00",
        "data_agendamento_final": f"{d} 23:59:59",
        "contrato_id": "",
        "os_id": "",
        "tipoos": "",
        "usuario": "",
        "veiculo": "",
    }

def parse_table_rows(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    table = soup.select_one("table#DataTables_Table_0") or soup.select_one("table")
    if not table:
        raise Exception("Não achei nenhuma tabela na página. Precisamos ajustar o seletor do table.")

    header_cells = table.select("thead th")
    headers = [h.get_text(strip=True) for h in header_cells]

    rows = []
    for tr in table.select("tbody tr"):
        tds = tr.select("td")
        if not tds:
            continue

        values = []
        for i, td in enumerate(tds):
            header = headers[i] if i < len(headers) else ""
            separator = "\n" if is_auxiliar_header(header) else " "
            values.append(td.get_text(separator, strip=True))
        row = {headers[i]: (values[i] if i < len(values) else "") for i in range(len(headers))}
        rows.append(row)

    return rows


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold()


def is_auxiliar_header(header: str) -> bool:
    normalized = normalize_text(header)
    return "tecnico" in normalized and "auxiliar" in normalized


def find_auxiliar_key(row: dict) -> str | None:
    for key in row.keys():
        if is_auxiliar_header(key):
            return key
    return None


def find_key_like(row: dict, wanted: str) -> str | None:
    wanted_normalized = normalize_text(wanted)
    for key in row.keys():
        if normalize_text(key) == wanted_normalized:
            return key
    return None


def row_value(row: dict, wanted: str) -> str:
    key = find_key_like(row, wanted)
    if not key:
        return ""
    return (row.get(key) or "").strip()


def first_name(nome: str) -> str:
    for parte in re.split(r"\s+", nome.strip()):
        if parte and re.search(r"[A-Za-zÀ-ÿ]", parte):
            return parte.title()
    return ""


def format_tecnicos(tecnicos: list[str] | None) -> str:
    nomes = [first_name(t) for t in (tecnicos or [])]
    nomes = [n for n in nomes if n]

    if not nomes:
        return ""
    if len(nomes) == 1:
        return nomes[0]
    if len(nomes) == 2:
        return f"{nomes[0]} e {nomes[1]}"
    return ", ".join(nomes[:-1]) + f" e {nomes[-1]}"


def extract_team_tecnicos(rows: list[dict], equipe_nome: str) -> list[str]:
    tecnicos = []
    vistos = set()

    for row in rows:
        if row_value(row, "Responsavel") != equipe_nome:
            continue

        aux_key = find_auxiliar_key(row)
        if not aux_key:
            continue

        for nome_completo in row.get(aux_key, "").splitlines():
            nome = first_name(nome_completo)
            if nome and nome not in vistos:
                tecnicos.append(nome)
                vistos.add(nome)
            if len(tecnicos) == 2:
                return tecnicos

    return tecnicos

def fibra_num_from_pop(pop_text: str) -> str | None:
    m = re.search(r"Fibra\s*(\d+)", pop_text, re.IGNORECASE)
    if m:
        return m.group(1)
    m2 = re.search(r"(\d+)", pop_text)
    return m2.group(1) if m2 else None

def classify_motivo(motivo: str) -> str:
    m = motivo.strip()

    if m.startswith("Mudança Endereço - casa"):
        return "Mudança Endereço - casa"
    if m.startswith("Mudança Endereço - apartamento/prédio geral"):
        return "Mudança Endereço - apartamento/prédio geral"
    if m.startswith("Mudança Endereço - apartamento Condomínios"):
        return "Mudança Endereço - apartamento Condomínios"
    if m.startswith("Instalação de KIT - apartamento Condomínios"):
        return "Instalação de KIT - apartamento Condomínios"
    if m.startswith("Instalação de KIT - casa"):
        return "Instalação de KIT - casa"
    if m.startswith("Instalação de KIT - apartamento/prédio geral"):
        return "Instalação de KIT - apartamento/prédio geral"
    if m.startswith("Remoção de KIT"):
        return "Remoção de KIT"
    if m.startswith("Entrega de Carnê físico"):
        return "Entrega de Carnê físico"
    

    return "Corretiva"

def build_team_report(
    rows: list[dict],
    equipe_nome: str,
    veiculo: str | None = None,
    tecnicos: list[str] | None = None
) -> str:
    equipe_rows = [r for r in rows if row_value(r, "Responsavel") == equipe_nome]
    total_os = len(equipe_rows)

    contagem = {
        "Corretiva": 0,
        "Mudança Endereço - apartamento/prédio geral": 0,
        "Mudança Endereço - casa": 0,
        "Mudança Endereço - apartamento Condomínios": 0,
        "Instalação de KIT - apartamento Condomínios": 0,
        "Instalação de KIT - casa": 0,
        "Instalação de KIT - apartamento/prédio geral": 0,
        "Remoção de KIT": 0,
        "Entrega de Carnê físico": 0,
    }

    fibras = []
    for r in equipe_rows:
        motivo = row_value(r, "Motivo")
        categoria = classify_motivo(motivo)

        if categoria in contagem:
            contagem[categoria] += 1
        else:
            contagem["Corretiva"] += 1

        pop = row_value(r, "Pop") or row_value(r, "POP")
        fibra = fibra_num_from_pop(pop)
        if fibra:
            fibras.append(fibra)

    fichas_inclusas = (
        contagem["Instalação de KIT - apartamento Condomínios"]
        + contagem["Instalação de KIT - casa"]
        + contagem["Instalação de KIT - apartamento/prédio geral"]
    )

    fibras_unicas = sorted(set(fibras), key=int)
    fibras_fmt = "; ".join(f"{int(x):02d}" for x in fibras_unicas)

    tecnicos_txt = format_tecnicos(tecnicos)
    veiculo_txt = f"({veiculo}) " if veiculo else ""

    linhas = []
    linhas.append(f"{equipe_nome} {veiculo_txt}{tecnicos_txt}".strip())

    if contagem["Corretiva"]:
        linhas.append(f"{contagem['Corretiva']:02d} Corretiva finalizadas")
    if contagem["Instalação de KIT - apartamento Condomínios"]:
        linhas.append(f"{contagem['Instalação de KIT - apartamento Condomínios']:02d} Instalação de KIT - apartamento Condomínios")
    if contagem["Instalação de KIT - casa"]:
        linhas.append(f"{contagem['Instalação de KIT - casa']:02d} Instalação de KIT - casa")
    if contagem["Instalação de KIT - apartamento/prédio geral"]:
        linhas.append(f"{contagem['Instalação de KIT - apartamento/prédio geral']:02d} Instalação de KIT - apartamento/prédio geral")
    if contagem["Mudança Endereço - casa"]:
        linhas.append(f"{contagem['Mudança Endereço - casa']:02d} Mudança Endereço - casa")
    if contagem["Remoção de KIT"]:
        linhas.append(f"{contagem['Remoção de KIT']:02d} Remoção de KIT")
    if contagem["Entrega de Carnê físico"]:
        linhas.append(f"{contagem['Entrega de Carnê físico']:02d} Entrega de Carnê físico")
    if contagem["Mudança Endereço - apartamento/prédio geral"]:
        linhas.append(f"{contagem['Mudança Endereço - apartamento/prédio geral']:02d} Mudança Endereço - apartamento/prédio geral")
    if contagem["Mudança Endereço - apartamento Condomínios"]:
        linhas.append(f"{contagem['Mudança Endereço - apartamento Condomínios']:02d} Mudança Endereço - apartamento Condomínios")    

    linhas.append(f"Total de ordens finalizadas= {total_os:02d}/Total de fichas inclusas= {fichas_inclusas:02d}")
    linhas.append("Check ins incorretos(SGP): 01")
    linhas.append(f"Fibras atendidas: {fibras_fmt}")

    return "\n".join(linhas)

def is_os_valida(r: dict) -> bool:
    resp = row_value(r, "Responsavel").upper()
    return resp in {f"EQUIPE {c}" for c in "ABCDEFGHI"}

def extract_equipes(rows: list[dict]) -> list[str]:
    equipes = {
        row_value(r, "Responsavel").upper()
        for r in rows
        if row_value(r, "Responsavel")
    }
    return sorted(
        [e for e in equipes if re.fullmatch(r"EQUIPE [A-I]", e)],
        key=lambda nome: nome.split()[-1],
    )



def build_resumo_geral(rows_concluidas: list[dict], hoje: datetime) -> str:
    amanha = hoje + timedelta(days=1)
    ontem = hoje - timedelta(days=1)

    # fixos como você pediu
    total_previstas_ontem = 45
    fichas_encaminhadas_grupo = 8

    # contar só ordens válidas (equipes A-I)
    rows_validas = [r for r in rows_concluidas if is_os_valida(r)]

    contagem = {
        "Corretiva": 0,
        "Mudança Endereço - apartamento/prédio geral": 0,
        "Mudança Endereço - casa": 0,
        "Mudança Endereço - apartamento Condomínios": 0,
        "Instalação de KIT - apartamento Condomínios": 0,
        "Instalação de KIT - casa": 0,
        "Instalação de KIT - apartamento/prédio geral": 0,
        "Remoção de KIT": 0,
        "Entrega de Carnê físico": 0,
    }

    for r in rows_validas:
        motivo = row_value(r, "Motivo")
        categoria = classify_motivo(motivo)

        if categoria in contagem:
            contagem[categoria] += 1
        else:
            contagem["Corretiva"] += 1

    # total finalizadas no dia = soma dos motivos (do jeito que você quer)
    total_finalizadas = sum(contagem.values())

    # total instalações finalizadas = soma das instalações
    total_instalacoes = (
        contagem["Instalação de KIT - apartamento Condomínios"]
        + contagem["Instalação de KIT - casa"]
        + contagem["Instalação de KIT - apartamento/prédio geral"]
    )

    # fichas inclusas no sgp = instalações (pela sua regra)
    fichas_sgp = total_instalacoes

    texto = (
        f"Relatório exclusivo das ordens CONCLUÍDAS! Todas as outras ordens pendentes ja foram realocadas para o dia {amanha.strftime('%d/%m')}!\n"
        f"Total de ordens previstas ontem ({ontem.strftime('%d/%m')}): {total_previstas_ontem}\n"
        f"Total de ordens finalizadas no dia: {total_finalizadas}\n"
        f"Total de instalações finalizadas: {total_instalacoes}\n"
        f"Total de fichas inclusas no sgp: {fichas_sgp}\n"
        f"Total de fichas encaminhadas no grupo: {fichas_encaminhadas_grupo:02d}"
    )
    return texto

# =========================
# 3) CONFIG: EQUIPES A - I
# =========================
EQUIPES = {
    "EQUIPE A": {"veiculo": "Kwid G11", "tecnicos": []},
    "EQUIPE B": {"veiculo": "Mobi G09", "tecnicos": ["Hugo e", "Ricardo"]},
    "EQUIPE C": {"veiculo": "Celta", "tecnicos": ["Anderson e", "Arthur"]},
    "EQUIPE D": {"veiculo": "Strada", "tecnicos": ["Hugo e", "José Andrade"]},
    "EQUIPE E": {"veiculo": "Mobi G04", "tecnicos": ["Diego e", "Paulo"]},
    "EQUIPE F": {"veiculo": "Mobi G12", "tecnicos": ["Wesllys e", "Cezar"]},
    "EQUIPE G": {"veiculo": "Kwid G13", "tecnicos": ["Filipe"]},
    "EQUIPE H": {"veiculo": "", "tecnicos": []},
    "EQUIPE I": {"veiculo": "Fiorino G02", "tecnicos": ["Jhonny e", "Wesley"]},
}


# =========================
# MAIN
# =========================
def main():
    session = requests.Session()
    login_sgp(session)

    hoje = agora_br()
    params = build_params_for_day(hoje)

    r_rep = session.get(REPORT_URL, params=params, verify=ssl_verify_enabled())
    r_rep.raise_for_status()

    rows = parse_table_rows(r_rep.text)


    print("#" * 60)
    print(build_resumo_geral(rows_concluidas=rows, hoje=hoje))
    print("#" * 60)
    print()

    # gera relatório das equipes encontradas no dia
    for equipe_nome in extract_equipes(rows):
        info = EQUIPES.get(equipe_nome, {"veiculo": "", "tecnicos": []})
        tecnicos = extract_team_tecnicos(rows, equipe_nome) or info.get("tecnicos")
        rel = build_team_report(
            rows=rows,
            equipe_nome=equipe_nome,
            veiculo=info.get("veiculo"),
            tecnicos=tecnicos,
        )

        # pula equipes sem OS no dia
        if "Total de ordens finalizadas= 00" in rel:
            continue

        print("=" * 60)
        print(rel)
        print()  # linha em branco


if __name__ == "__main__":
    main()


