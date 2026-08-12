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
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# --- torna os módulos de comum/ importáveis e carrega o .env da raiz ---
# (este arquivo fica em automacoes/vendas/ ; comum/ e .env ficam em automacoes/)
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RAIZ, "comum"))
load_dotenv(os.path.join(_RAIZ, ".env"))

# O console do Windows (cp1252) NÃO imprime emoji/caractere exótico — e nomes de
# WhatsApp têm muito disso. Sem isto, um único contato com emoji derruba o
# relatório inteiro com UnicodeEncodeError. UTF-8 + replace = nunca quebra.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

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

# ------------------------------------------------------------------
# DETECÇÃO "SEM COBERTURA / NÃO ATENDEMOS A REGIÃO"
# ------------------------------------------------------------------
# Varre as mensagens do atendimento e marca (etiqueta) quem foi recusado por
# cobertura/localização. Só olha as falas NOSSAS (a recusa vem do atendente) e
# usa FRASES de recusa — nunca a palavra "região" solta (aparece em saudação).
#
# >>> Fácil de ajustar: é só somar/tirar frases nas listas abaixo. <<<
# Tudo é comparado sem acento e em minúsculas (via normalizar()).
#
# FORTES = recusa explícita (basta uma p/ marcar).
FRASES_FORTES = [
    r"sem cobertura",
    r"nao (temos|tem|ha) cobertura",
    r"fora da (nossa )?(area|cobertura|regiao)",
    r"sem viabilidade",
    r"nao (ha|tem|possui|temos) viabilidade",
    r"inviavel",
    # até 3 palavras entre o "não atendemos" e a "região" — cobre "nao atendemos
    # AINDA NESSA regiao" e "nao atendemos A SUA regiao", que a lista fixa de
    # preposições deixava passar (visto em atendimento real). Vírgula/ponto
    # interrompem o \w+, então a frase não "pula" pra outra oração.
    r"nao atend\w*(?: \w+){0,3}? (regiao|localidade|area|local)\b",
    r"nao cheg\w+ (na|na sua|ate|nessa|a sua|nesse|no)",
    r"nao cobre",
    r"nao alcan\w+",
    r"regiao nao atendida",
    r"nao contempl\w+",
    r"nao (temos|tem) (rede|estrutura|sinal|internet)",
    r"dificil acesso",
]
# FRACAS = pistas de "longe" que indicam recusa; só marcam se NÃO houver negação
# perto. Evita "de longe (a melhor)" e "distante do roteador" de propaganda.
FRASES_FRACAS = [
    r"um pouco longe", r"muito longe", r"meio longe", r"bem longe",
    r"longe demais", r"\bfica longe\b", r"\bficou longe\b",
    r"\besta longe\b", r"\bta longe\b",
]
# NEGACOES = se a mensagem tiver isto, ignora as pistas fracas (é o contrário).
# Precisa cobrir TODAS as formas verbais das FRACAS acima — senão "nao esta longe
# nao, atendemos sim" era marcado como SEM COBERTURA (o oposto do que foi dito).
NEGACOES = ["perto", "pertinho", "nao e longe", "nao fica longe", "nao muito longe",
            "nao esta longe", "nao ta longe", "nao ficou longe"]

_RE_FORTE = re.compile("|".join(FRASES_FORTES), re.IGNORECASE)
_RE_FRACO = re.compile("|".join(FRASES_FRACAS), re.IGNORECASE)


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

    O WhatsApp devolve a MAIORIA dos números no formato antigo, sem o 9º dígito
    ('556192836157'). Como o relatório é feito pra colar/discar, o 9 é recolocado
    nos celulares (8 dígitos começando em 8 ou 9). Fixo (começa em 2–5) fica igual.
    Isso não atrapalha o SGP: sgp_api._variacoes_telefone() consulta as duas formas."""
    d = re.sub(r"\D", "", num or "")
    if d.startswith("55") and len(d) > 11:
        d = d[2:]
    if len(d) == 10 and d[2] in "89":     # celular no formato antigo: falta o 9
        d = d[:2] + "9" + d[2:]
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

    # O token do FocusChat é POR CANAL (número de WhatsApp). Lemos TODOS os canais
    # configurados (FOCUS_TOKEN/FOCUS_TOKENS) — senão as vendas de um canal que o
    # token não cobre ficam invisíveis (foi o bug do "canal de backup").
    if not focus_api.TOKENS:
        raise SystemExit("Nenhum token do FocusChat no .env (FOCUS_TOKEN/FOCUS_TOKENS).")
    print(f"Lendo {len(focus_api.TOKENS)} canal(is) do FocusChat:")
    for tok in focus_api.TOKENS:
        try:
            print(f"  - {focus_api.nome_canal(tok)}")
        except Exception:
            print("  - (canal não identificado)")

    resultados = {}
    for sid in ids:
        # status FINALIZADO = histórico de atendimentos concluídos (o que
        # interessa pra conferir venda). Pra incluir os abertos, trocar por
        # focus_api.STATUS_ATENDIDOS.
        chats = focus_api.listar_chats_todos_canais(
            sector_id=sid, status=focus_api.STATUS_FINALIZADO,
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
            # mantém o mais recente por contato (chats vêm do mais novo).
            # _token/_canal = de qual canal veio (pra ler as mensagens depois).
            resultados.setdefault(chave, {
                "nome": limpar_nome(nome),
                "numero": _formatar_numero(numero),
                "data": data_str,
                "attendance_id": chat.get("attendanceId"),
                "_token": chat.get("_token"),
                "_canal": chat.get("_canal"),
            })
            print(f"  [{len(resultados)}] {limpar_nome(nome)} | "
                  f"{_formatar_numero(numero)} | {data_str}")

    linhas = list(resultados.values())
    with open(ARQUIVO_VENDAS, "w", newline="", encoding="utf-8-sig") as f:
        # extrasaction="ignore": a linha carrega campos internos (attendance_id)
        # que não vão pro backup — o writer ignora o que não está em fieldnames.
        w = csv.DictWriter(f, fieldnames=["nome", "numero", "data"],
                           extrasaction="ignore")
        w.writeheader()
        for linha in linhas:
            w.writerow(linha)
    print(f"\nLista de VENDAS salva em {ARQUIVO_VENDAS} - {len(linhas)} atendimento(s).")
    return linhas


# ============================================================
# COBERTURA (lê as mensagens da conversa e etiqueta a recusa por região)
# ============================================================
def detectar_sem_cobertura(mensagens):
    """
    Varre as mensagens NOSSAS do atendimento e devolve (True, trecho) no 1º sinal
    de sem cobertura / inviabilidade por localização. Ignora mensagens de sistema
    e do cliente, e descarta as pistas fracas (longe) quando há negação perto.
    """
    for m in mensagens or []:
        if not m.get("isSentByMe") or m.get("isSystemMessage"):
            continue
        texto = (m.get("text") or "").strip()
        if not texto:
            continue
        alvo = normalizar(texto)
        forte = _RE_FORTE.search(alvo)
        fraco = _RE_FRACO.search(alvo) and not any(n in alvo for n in NEGACOES)
        if forte or fraco:
            return True, re.sub(r"\s+", " ", texto)[:160]
    return False, ""


# ------------------------------------------------------------------
# LOCAL (região citada na conversa)
# ------------------------------------------------------------------
# Regiões conhecidas da GIGANET. Chaves em minúsculo/sem acento (casam com
# normalizar()). Ordem importa: o mais específico vem antes (ex. "itapoa parque"
# antes de "itapoa"; "planaltina go" antes de "planaltina"). Fácil de estender.
REGIOES = [
    (["itapoa parque"], "Itapoã Parque"),
    (["total ville", "totalville", "total vile"], "Total Ville"),
    (["del lago ii", "del lago 2"], "Del Lago II"),
    (["del lago i", "del lago 1", "del lago"], "Del Lago I"),
    (["fazendinha"], "Fazendinha"),
    (["mestre d armas", "mestre d'armas", "mestre darmas"], "Mestre D'Armas"),
    (["nova planaltina"], "Nova Planaltina"),
    (["arapongas"], "Arapongas"),
    (["estancia"], "Estância"),
    (["vale do amanhecer"], "Vale do Amanhecer"),
    (["planaltina go", "planaltina goias", "planaltina de goias"], "Planaltina GO"),
    (["planaltina"], "Planaltina DF"),
    (["itapoa"], "Itapoã"),
    (["sobradinho"], "Sobradinho"),
    (["paranoa"], "Paranoá"),
]


def _normalizar_busca(texto: str) -> str:
    """normalizar() + separadores viram espaço, p/ as chaves de REGIOES casarem
    com o jeito que se digita no WhatsApp. Sem isto, 'del lago-2' e 'del lago2'
    não batiam na chave 'del lago 2' e caíam na genérica 'del lago' → o relatório
    dizia Del Lago I no lugar de Del Lago II. Idem 'planaltina-go' virando DF."""
    t = normalizar(texto)
    t = re.sub(r"[-_./\\]+", " ", t)           # hífen/barra/ponto viram espaço
    t = re.sub(r"(?<=[a-z])(?=\d)", " ", t)    # 'lago2'  -> 'lago 2'
    t = re.sub(r"(?<=\d)(?=[a-z])", " ", t)    # '2quadra'-> '2 quadra'
    return " ".join(t.split())


def _extrair_local(textos) -> str:
    """Procura uma região conhecida no texto da conversa. '' se não achar.

    Cada mensagem é separada por ' | ' de propósito: sem isso o fim de uma
    mensagem colava no começo da outra e inventava região ('moro no total' +
    'ville fica perto' virava Total Ville)."""
    blob = _normalizar_busca(" | ".join(t for t in textos if t))
    for chaves, nome in REGIOES:
        if any(k in blob for k in chaves):
            return nome
    return ""


def analisar_cobertura(linhas, workers=6):
    """
    Lê as mensagens de cada atendimento (1 GET por conversa, em paralelo) e, no
    MESMO passo, marca: `sem_cobertura` ('SIM'/'') + `trecho_cobertura` (a fala que
    provou) e `local` (região citada na conversa). Não altera o resto da linha.
    """
    def _uma(linha):
        linha.setdefault("sem_cobertura", "")
        linha.setdefault("trecho_cobertura", "")
        linha.setdefault("local", "")
        aid = linha.get("attendance_id")
        if not aid:
            return
        try:
            # usa o token do MESMO canal do chat (um token só lê o seu canal)
            msgs = focus_api.mensagens_do_chat(aid, token=linha.get("_token"))
        except Exception as e:
            linha["trecho_cobertura"] = f"(erro ao ler conversa: {e})"
            return
        # mesma leitura serve p/ cobertura E local. Vale primeiro o que o CLIENTE
        # falou: quando as duas partes citam regiões diferentes (o atendente
        # comparando, p.ex.), quem manda é onde o cliente mora. Só se ele não
        # disser nada é que olhamos a conversa inteira (o atendente costuma
        # repetir a região do cliente).
        linha["local"] = (
            _extrair_local([m.get("text") or "" for m in msgs if not m.get("isSentByMe")])
            or _extrair_local([m.get("text") or "" for m in msgs])
        )
        achou, trecho = detectar_sem_cobertura(msgs)
        if achou:
            linha["sem_cobertura"] = "SIM"
            linha["trecho_cobertura"] = trecho

    print(f"\nLendo as conversas p/ checar cobertura e local ({len(linhas)} atendimento(s))...")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(_uma, linhas))
    n = sum(1 for l in linhas if l.get("sem_cobertura") == "SIM")
    print(f"  -> {n} conversa(s) com sinal de SEM COBERTURA / não atendemos a região.")
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

    # 2b) lê as conversas dos não-clientes e etiqueta recusa por cobertura/região
    analisar_cobertura(nao_clientes)

    # 3) salva o CSV e imprime o relatório final (formato p/ colar no WhatsApp)
    campos = ["nome", "numero", "data", "local", "status_sgp",
              "sem_cobertura", "trecho_cobertura"]
    with open(SAIDA_FINAL, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for linha in nao_clientes:
            w.writerow({c: linha.get(c, "") for c in campos})

    data_titulo = filtro.replace("/", ";") if filtro else "todas"
    print(f"\n📋 VENDAS QUE NÃO FINALIZADAS ({data_titulo})")
    if not nao_clientes:
        print("Nenhum! Todos os atendidos viraram clientes. :)")
    else:
        for linha in nao_clientes:
            nome = (linha.get("nome") or "").strip() or "sem nome"
            numero = (linha.get("numero") or "").strip()
            numero = f"+55 {numero}" if numero else "(sem número)"
            local = (linha.get("local") or "").strip() or "não informou o local"
            tag = " [SEM COBERTURA]" if linha.get("sem_cobertura") == "SIM" else ""
            print(f"{nome} {numero} {local}{tag}")
    n_cob = sum(1 for l in nao_clientes if l.get("sem_cobertura") == "SIM")
    print(f"\n({len(nao_clientes)} não finalizadas · {n_cob} sem cobertura · "
          f"backup em {ARQUIVO_VENDAS})")


if __name__ == "__main__":
    main()
