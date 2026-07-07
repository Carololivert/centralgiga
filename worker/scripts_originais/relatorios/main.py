#!/usr/bin/env python3
"""
main.py — Relatório de produção do dia por equipe (GIGANET).

Migrado para a API oficial do SGP (endpoint /api/os/list/, via comum/sgp_api.py).
NÃO usa mais login web nem raspagem de HTML, então NÃO depende de 2FA.

Uso:
    python relatorios\\main.py
"""

import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --- torna comum/ importável e carrega o .env da raiz ---
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RAIZ, "comum"))
from dotenv import load_dotenv
load_dotenv(os.path.join(_RAIZ, ".env"))

from sgp_api import listar_os

TZ_BR = ZoneInfo("America/Sao_Paulo")


def agora_br() -> datetime:
    return datetime.now(TZ_BR).replace(tzinfo=None)


# ============================================================
# ADAPTADOR: OS da API -> mesmas "colunas" que a lógica usa
# ============================================================
def _adaptar(os_item: dict) -> dict:
    aux = os_item.get("tecnicos_auxiliares") or []
    return {
        "Responsavel": (os_item.get("responsavel") or "").strip(),
        "Motivo": (os_item.get("motivo") or "").strip(),
        "Pop": (os_item.get("pop") or "").strip(),
        "Tecnico Auxiliar": "\n".join(a for a in aux if a),
    }


# ============================================================
# HELPERS (iguais aos seus)
# ============================================================
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


def build_team_report(rows, equipe_nome, veiculo=None, tecnicos=None) -> str:
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
        categoria = classify_motivo(row_value(r, "Motivo"))
        if categoria in contagem:
            contagem[categoria] += 1
        else:
            contagem["Corretiva"] += 1
        fibra = fibra_num_from_pop(row_value(r, "Pop") or row_value(r, "POP"))
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

    total_previstas_ontem = 45
    fichas_encaminhadas_grupo = 8

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
        categoria = classify_motivo(row_value(r, "Motivo"))
        if categoria in contagem:
            contagem[categoria] += 1
        else:
            contagem["Corretiva"] += 1

    total_finalizadas = sum(contagem.values())
    total_instalacoes = (
        contagem["Instalação de KIT - apartamento Condomínios"]
        + contagem["Instalação de KIT - casa"]
        + contagem["Instalação de KIT - apartamento/prédio geral"]
    )
    fichas_sgp = total_instalacoes

    return (
        f"Relatório exclusivo das ordens CONCLUÍDAS! Todas as outras ordens pendentes ja foram realocadas para o dia {amanha.strftime('%d/%m')}!\n"
        f"Total de ordens previstas ontem ({ontem.strftime('%d/%m')}): {total_previstas_ontem}\n"
        f"Total de ordens finalizadas no dia: {total_finalizadas}\n"
        f"Total de instalações finalizadas: {total_instalacoes}\n"
        f"Total de fichas inclusas no sgp: {fichas_sgp}\n"
        f"Total de fichas encaminhadas no grupo: {fichas_encaminhadas_grupo:02d}"
    )


# ============================================================
# CONFIG: EQUIPES A - I
# ============================================================
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


# ============================================================
# MAIN
# ============================================================
def main():
    hoje = agora_br()
    dia = hoje.strftime("%Y-%m-%d")   # formato que a API espera

    # Todas as OS agendadas para hoje
    os_list = listar_os(
        data_agendamento_inicio=dia,
        data_agendamento_fim=dia,
    )
    rows = [_adaptar(o) for o in os_list]

    print("#" * 60)
    print(build_resumo_geral(rows_concluidas=rows, hoje=hoje))
    print("#" * 60)
    print()

    for equipe_nome in extract_equipes(rows):
        info = EQUIPES.get(equipe_nome, {"veiculo": "", "tecnicos": []})
        tecnicos = extract_team_tecnicos(rows, equipe_nome) or info.get("tecnicos")
        rel = build_team_report(
            rows=rows,
            equipe_nome=equipe_nome,
            veiculo=info.get("veiculo"),
            tecnicos=tecnicos,
        )
        if "Total de ordens finalizadas= 00" in rel:
            continue
        print("=" * 60)
        print(rel)
        print()


if __name__ == "__main__":
    main()