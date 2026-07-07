#!/usr/bin/env python3
"""
vendas_focus_sgp.py

Fluxo COMPLETO num comando só:

  1) Lista os atendimentos dos setores de VENDAS no FocusChat via API oficial
     (comum/focus_api.py) e coleta NOME + NÚMERO + DATA de cada um.
  2) Salva a lista bruta em vendas_do_dia.csv (backup).
  3) Consulta cada número no SGP (via API Token/App) e gera o relatório FINAL
     só com quem NÃO tem cadastro (não virou cliente).

  >>> As DUAS pontas agora usam API oficial (FocusChat e SGP). NÃO passam mais
      pelo login web, então NÃO dependem de 2FA nem de Playwright/raspagem.

Uso:
    python vendas_focus_sgp.py                 # data de hoje
    python vendas_focus_sgp.py 03/06/2026      # uma data específica
    python vendas_focus_sgp.py todas           # não filtra por data (pega tudo)

Dependências:
    pip install requests python-dotenv tzdata

Credenciais (no .env da raiz):
    FOCUS_TOKEN=token_do_canal_do_focuschat
    # SGP (usados pelo sgp_api.py):
    SGP_BASE=https://giganetwireless.sgp.net.br
    SGP_TOKEN=seu_token
    SGP_APP=seu_app
    # opcional: SGP_VERIFY_SSL=false   (se der erro de certificado)
"""

import os
import re
import sys
import csv
import time
import unicodedata
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# --- torna os módulos de comum/ importáveis e carrega o .env da raiz ---
# (este arquivo fica em automacoes/vendas/ ; comum/ e .env ficam em automacoes/)
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RAIZ, "comum"))
load_dotenv(os.path.join(_RAIZ, ".env"))

# Checagem no SGP via API oficial (Token/App). Vem de comum/sgp_api.py.
from sgp_api import eh_cliente
# Coleta dos atendimentos via API oficial do FocusChat. Vem de comum/focus_api.py.
import focus_api

# ============================================================
# CONFIGURAÇÃO
# ============================================================
# Nomes dos setores de VENDAS no FocusChat. O match ignora acentos e caixa,
# então "VENDAS PLANTAO" casa com "VENDAS PLANTÃO".
SETORES_VENDAS = ["VENDAS", "VENDAS PLANTAO"]

# Fuso pra converter a data UTC do atendimento (utcDhStartChat) em data local.
TZ = ZoneInfo("America/Sao_Paulo")

ARQUIVO_VENDAS = "vendas_do_dia.csv"     # backup da lista bruta de VENDAS
SAIDA_FINAL    = "relatorio_final.csv"   # relatório final (não-clientes)


# ============================================================
# UTILIDADES
# ============================================================
def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(t.lower().split())

def limpar_nome(nome: str) -> str:
    return re.sub(r"[^\w\s\.\-']", "", nome or "", flags=re.UNICODE).strip()

def _data_obj(s):
    """'dd/mm/aaaa' -> date, ou None."""
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except Exception:
        return None

def _data_local(utc_str: str):
    """Converte o utcDhStartChat (ex '2026-07-04T12:08:28.435', em UTC) na
    data local (America/Sao_Paulo). Devolve um date ou None."""
    if not utc_str:
        return None
    try:
        dt = datetime.fromisoformat(utc_str.strip().replace("Z", ""))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(TZ).date()

def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _formatar_numero(num: str) -> str:
    """Deixa o número legível: '5561984880820' -> '(61) 98488-0820'.
    (a checagem no SGP normaliza de novo, então o formato aqui é só cosmético.)"""
    d = re.sub(r"\D", "", num or "")
    if d.startswith("55") and len(d) > 11:
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return num or ""


# ============================================================
# FOCUSCHAT (coleta via API oficial)
# ============================================================
def coletar_vendas(filtro_data):
    """Lista os atendimentos de VENDAS no FocusChat (API) e devolve lista de
    dicts {nome, numero, data}. Também salva o backup em ARQUIVO_VENDAS.

    filtro_data: 'dd/mm/aaaa' pra um dia, ou None pra não filtrar por data."""
    alvo = _data_obj(filtro_data) if filtro_data else None

    ids = focus_api.achar_setores(*SETORES_VENDAS)
    if not ids:
        raise SystemExit(f"Nenhum setor de VENDAS encontrado no FocusChat "
                         f"(procurei por {SETORES_VENDAS}). Rode "
                         f"'python comum/focus_api.py' pra ver os nomes.")

    # Pra um dia específico, pede uma janela UTC folgada (±1 dia) e depois
    # filtra a data exata no cliente, evitando erro de fuso na virada do dia.
    di = df = None
    if alvo:
        di = _iso_utc(datetime.combine(alvo, dtime.min, TZ) - timedelta(days=1))
        df = _iso_utc(datetime.combine(alvo, dtime.max, TZ) + timedelta(days=1))

    resultados = {}
    for sid in ids:
        # status FINALIZADO = histórico de atendimentos concluídos (o que
        # interessa pra conferir venda). Pra incluir os abertos, trocar por
        # focus_api.STATUS_ATENDIDOS.
        chats = focus_api.listar_chats(sector_id=sid,
                                       status=focus_api.STATUS_FINALIZADO,
                                       data_inicio=di, data_fim=df)
        for chat in chats:
            nome, numero = focus_api.contato_do_chat(chat)
            d_item = _data_local(chat.get("utcDhStartChat") or "")
            if alvo and d_item and d_item != alvo:
                continue
            data_str = d_item.strftime("%d/%m/%Y") if d_item else ""
            chave = re.sub(r"\D", "", numero) or normalizar(nome)
            if not chave:
                continue
            # mantém o mais recente por contato (chats vêm do mais novo)
            resultados.setdefault(chave, {
                "nome": limpar_nome(nome),
                "numero": _formatar_numero(numero),
                "data": data_str,
            })
            print(f"  [{len(resultados)}] {limpar_nome(nome)} | "
                  f"{_formatar_numero(numero)} | {data_str}")

    linhas = list(resultados.values())
    with open(ARQUIVO_VENDAS, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["nome", "numero", "data"])
        w.writeheader()
        for linha in linhas:
            w.writerow(linha)
    print(f"\nLista de VENDAS salva em {ARQUIVO_VENDAS} - {len(linhas)} atendimento(s).")
    return linhas


# ============================================================
# SGP (checagem via API Token/App)
# ============================================================
def checar_no_sgp(linhas):
    """Recebe a lista de vendas e devolve só quem NÃO é cliente.
    Usa a API oficial do SGP (sgp_api.eh_cliente) — sem login web, sem 2FA."""
    print(f"\n{len(linhas)} contato(s) para conferir no SGP...")

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
            ja_cliente = eh_cliente(numero)
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

    # 1) coleta no FocusChat (API)
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
