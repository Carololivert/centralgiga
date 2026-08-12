#!/usr/bin/env python3
"""
streaming_ativacao.py — Relatório diário de ATIVAÇÃO DE STREAMING.

Pega os cadastros NOVOS do dia e, para cada um cujo plano inclui streaming
(Globoplay, Max/HBO, Telecine, Watch, Premiere, Disney+), joga no relatório com
o que a equipe precisa pra ativar: NOME, E-MAIL, TELEFONE, POP e o PLANO.

Plano sem streaming é DESCARTADO — não há TV para ativar.

Como acha os cadastros do dia (o caminho que funciona):
    /api/ura/clientes/ aceita `data_cadastro_inicio` e `data_cadastro_fim`.
    (O /api/ura/listacontrato/ dá TIMEOUT mesmo com limit=2, e o
     /api/suporte/contrato/list/ não filtra por data — não servem.)

O streaming sai do NOME DO PLANO: dos 150 planos do SGP, 62 já declaram o
streaming na descrição (ex.: "1 GIGA MAX + GLOBOPLAY"). Varre TODOS os serviços
do contrato, então pega também streaming vendido como serviço à parte
(ex.: plano "celetihub-globoplay").

Uso:
    python relatorios/streaming_ativacao.py                # hoje
    python relatorios/streaming_ativacao.py 20/07/2026     # um dia específico

Credenciais (no .env da raiz): SGP_BASE, SGP_TOKEN, SGP_APP.
"""

import os
import re
import sys
import csv
import unicodedata
from datetime import date, datetime

from dotenv import load_dotenv

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RAIZ, "comum"))
load_dotenv(os.path.join(_RAIZ, ".env"))

# Console do Windows (cp1252) quebra com emoji/acento em nome de cliente.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import sgp_api

SAIDA = "streaming_ativacao.csv"

# ============================================================
# DE-PARA DOS STREAMINGS
# ============================================================
# Comparado sem acento e em MAIÚSCULAS (via _norm). Fácil de ajustar: é só
# somar/tirar linha. A ORDEM importa pouco, mas TELECINE vem antes de "CINE"
# solto (que nem é usado, justamente pra não casar dentro de "TeleCINE").
#
# Prime Video e Apple TV+ entram como DISNEY+: são o mesmo combo "escolha um"
# (R$19,90) e a equipe trata tudo como Disney.
STREAMINGS_TV = [
    ("GLOBOPLAY", [r"GLOBO\s*PLAY"]),
    ("MAX (HBO)", [r"\bMAX\b", r"\bHBO\b"]),
    ("TELECINE",  [r"TELECINE"]),
    ("WATCH",     [r"\bWATCH\b"]),
    ("PREMIERE",  [r"PREMIERE"]),
    ("DISNEY+",   [r"DISNEY", r"PRIME\s*VIDEO", r"APPLE\s*TV"]),
]

# Extras de conteúdo que NÃO são TV: aparecem no relatório como informação,
# mas sozinhos NÃO colocam o cliente na lista (não há TV para ativar).
EXTRAS = [
    ("LIVROS", [r"LIVROS\s*DIGITAIS", r"SKEELO"]),
]

# OVERRIDE MANUAL: planos que INCLUEM streaming mas NÃO dizem no nome (o caso dos
# condomínios Itapoã Parque / Total Ville, onde o WATCH vem embutido). O SGP não
# tem campo de streaming, então aqui é a fonte da verdade pra esses.
# Chave = plano_id (estável); valor = lista de streamings.
# Confirmado com a equipe (2026-07-22): só os TOTAL VILLE 800 MEGAS incluem WATCH
# embutido; os Itapoã 700/800 NÃO têm streaming (a arte engana). Demais = nada.
OVERRIDE_STREAMINGS: dict[int, list] = {
    214: ["WATCH"],   # 2026 - TOTAL VILLE - 800 MEGAS - 119,99/99,99 - FIDR
    213: ["WATCH"],   # 2026 - TOTAL VILLE - 800 MEGAS - 119,99/99,99 - Sem fidelidade
}


def _norm(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "")
    return "".join(c for c in txt if not unicodedata.combining(c)).upper()


def detectar_streamings(descricao_plano: str):
    """Devolve (tv, extras) achados no nome do plano."""
    d = _norm(descricao_plano)
    tv = [nome for nome, pats in STREAMINGS_TV
          if any(re.search(p, d) for p in pats)]
    ex = [nome for nome, pats in EXTRAS
          if any(re.search(p, d) for p in pats)]
    return tv, ex


# ============================================================
# SGP
# ============================================================
def mapa_pops() -> dict:
    """{pop_id: nome do POP} — o cliente traz só o pop_id."""
    r = sgp_api.chamar("/api/ura/pops/")
    lista = r if isinstance(r, list) else (r.get("pops") or [])
    return {p.get("id"): p.get("pop") for p in lista if isinstance(p, dict)}


def clientes_novos(dia_iso: str) -> list:
    """Clientes cadastrados NO DIA (data_cadastro_inicio/fim = o mesmo dia)."""
    r = sgp_api.chamar("/api/ura/clientes/",
                       data_cadastro_inicio=dia_iso, data_cadastro_fim=dia_iso)
    return (r.get("clientes") or []) if isinstance(r, dict) else (r or [])


def _contato(cliente: dict):
    c = cliente.get("contatos") or {}
    email = next(iter(c.get("emails") or []), "")
    fone = next(iter((c.get("celulares") or []) + (c.get("telefones") or [])), "")
    return email, fone


def montar_linhas(dia_iso: str) -> tuple:
    """
    Aplica o filtro da equipe (igual ao admin/cliente/list): cadastro no dia +
    contrato ATIVO + serviço de INTERNET. Devolve (linhas_com_streaming,
    total_ativos_no_dia, pendentes) — pendentes = cadastros do dia ainda NÃO ativos.
    """
    pops = mapa_pops()
    clientes = clientes_novos(dia_iso)
    linhas, total_ativos, pendentes = [], 0, 0
    for cli in clientes:
        email, fone = _contato(cli)
        for ctr in (cli.get("contratos") or []):
            # só o que foi cadastrado no dia (o cliente pode ter contrato antigo)
            if str(ctr.get("dataCadastro") or "") != dia_iso:
                continue
            # só serviço de internet (ignora telefonia/streaming avulso na contagem)
            internet = [s for s in (ctr.get("servicos") or [])
                        if (s.get("tipo") or "").lower() == "internet"]
            if not internet:
                continue
            # só ATIVOS: cadastro Inativo/Cancelado NÃO ativa streaming (regra da equipe)
            if str(ctr.get("status") or "").strip().lower() != "ativo":
                pendentes += 1
                continue
            total_ativos += 1
            tv, extras, planos = [], [], []
            for serv in internet:
                plano = serv.get("plano") or {}
                desc = plano.get("descricao") or ""
                if not desc:
                    continue
                planos.append(desc)
                t, e = detectar_streamings(desc)
                # override manual: planos que têm streaming mas não dizem no nome
                t += [x for x in OVERRIDE_STREAMINGS.get(plano.get("id"), []) if x not in t]
                tv += [x for x in t if x not in tv]
                extras += [x for x in e if x not in extras]
            if not tv:            # sem TV pra ativar -> descarta
                continue
            linhas.append({
                "nome": cli.get("nome") or "",
                "email": email,
                "telefone": fone,
                "pop": pops.get(ctr.get("pop_id"), f"(pop {ctr.get('pop_id')})"),
                "contrato": ctr.get("id"),
                "streamings": " + ".join(tv),
                "extras": " + ".join(extras),
                "plano": " | ".join(planos),
                "data_cadastro": ctr.get("dataCadastro"),
            })
    return linhas, total_ativos, pendentes


# ============================================================
# MAIN
# ============================================================
def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    dia = datetime.strptime(arg, "%d/%m/%Y").date() if arg else date.today()
    dia_iso = dia.strftime("%Y-%m-%d")

    print(f"Cadastros novos de {dia.strftime('%d/%m/%Y')} (ativos + internet)...")
    linhas, total, pendentes = montar_linhas(dia_iso)

    campos = ["nome", "email", "telefone", "pop", "contrato",
              "streamings", "extras", "plano", "data_cadastro"]
    with open(SAIDA, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for linha in linhas:
            w.writerow(linha)

    print("\n" + "=" * 78)
    print("  ATIVACAO DE STREAMING - CADASTROS NOVOS DE " + dia.strftime("%d/%m/%Y"))
    print("=" * 78)
    if not linhas:
        print("  Nenhum cadastro novo com streaming hoje.")
    for i, l in enumerate(linhas, 1):
        print(f"  {i}. {l['nome']}  ->  {l['streamings']}"
              + (f"  (+{l['extras']})" if l["extras"] else ""))
        print(f"     e-mail: {l['email'] or '(sem e-mail)'}   tel: {l['telefone'] or '(sem tel)'}")
        print(f"     POP: {l['pop']}   contrato: {l['contrato']}")
        print(f"     plano: {l['plano']}")
    print("=" * 78)
    print(f"  {len(linhas)} de {total} cadastro(s) ATIVO(s) do dia tem streaming para ativar")
    if pendentes:
        print(f"  ({pendentes} cadastro(s) do dia ainda NAO ativo(s) -- entram quando ativarem)")
    print(f"  (relatorio salvo em {SAIDA})")
    print("=" * 78)


if __name__ == "__main__":
    main()
