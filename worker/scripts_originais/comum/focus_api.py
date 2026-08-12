"""
focus_api.py — Cliente da API oficial do FocusChat.

Por que a API: o `vendas` puxava atendimentos raspando a lista virtualizada
do painel (Playwright), que travava e só pegava ~15 de ~100. A API oficial
devolve NOME + NÚMERO prontos em cada chat, paginado, sem raspar nada.

Autenticação: header `access-token` = Token do Canal (gerado no FocusChat).
⚠️ O token é POR CANAL (número de WhatsApp): um token só enxerga os chats DAQUELE
canal. Se as vendas entram por vários números, configure vários tokens.
.env (na raiz):
    FOCUS_TOKEN=token_do_canal            # um canal só, OU
    FOCUS_TOKENS=tok_canal1,tok_canal2    # vários canais (separados por vírgula)

Referência: https://api.focuschat.com.br/swagger/index.html
Dependências:
    pip install requests python-dotenv
"""

import os
import re
import time
import unicodedata
import requests
from dotenv import load_dotenv

load_dotenv()


def _normaliza(txt: str) -> str:
    """Maiúsculas, sem acentos e sem espaços nas pontas — pra casar nomes."""
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return txt.strip().upper()

BASE = os.getenv("FOCUS_BASE", "https://api.focuschat.com.br").rstrip("/")


def _carregar_tokens() -> list:
    """
    Lê os tokens de canal do .env. Aceita FOCUS_TOKENS (lista separada por
    vírgula/;/espaço) e/ou FOCUS_TOKEN (um só). Junta os dois sem duplicar.
    """
    bruto = f"{os.getenv('FOCUS_TOKENS', '')},{os.getenv('FOCUS_TOKEN', '')}"
    toks, vistos = [], set()
    for t in re.split(r"[,;\s]+", bruto):
        t = t.strip()
        if t and t not in vistos:
            vistos.add(t)
            toks.append(t)
    return toks


TOKENS = _carregar_tokens()
TOKEN = TOKENS[0] if TOKENS else None   # compat: 1º token é o default das chamadas

# status do atendimento (campo `status` no filtro / na resposta):
#   0 automatico | 1 aguardando | 2 manual | 3 finalizado
#   4 pesquisa_satisfacao | 5 fora_de_hora
STATUS_AUTOMATICO = 0
STATUS_AGUARDANDO = 1
STATUS_MANUAL = 2
STATUS_FINALIZADO = 3
STATUS_FORA_DE_HORA = 5
# atendimentos "de verdade" (tudo menos o robô automático): usado quando se
# quer o histórico completo do dia, não só os finalizados.
STATUS_ATENDIDOS = [STATUS_AGUARDANDO, STATUS_MANUAL, STATUS_FINALIZADO,
                    STATUS_FORA_DE_HORA]

# tipo do atendimento (campo `typeChat`): 2 individual | 3 grupo.
# ATENÇÃO: a API do FocusChat retorna 500 (fatal_01) se `typeChat` OU `status`
# não forem enviados — por isso o cliente SEMPRE manda os dois.
TIPO_INDIVIDUAL = 2
TIPO_GRUPO = 3


def _headers(token: str | None = None) -> dict:
    tok = token or TOKEN
    if not tok:
        raise RuntimeError("Falta FOCUS_TOKEN/FOCUS_TOKENS no .env (Token do Canal do FocusChat)")
    return {"access-token": tok, "Content-Type": "application/json"}


def chamar(metodo: str, endpoint: str, json_body: dict | None = None,
           tentativas: int = 3, token: str | None = None) -> dict | list:
    """
    Chamador genérico da API do FocusChat (injeta o access-token do canal).
    Ex: chamar("GET", "/core/v2/api/sectors"). `token` escolhe o canal (default = 1º).

    A API do FocusChat às vezes devolve 500 passageiro ou dá timeout no meio de
    uma paginação longa. Para não derrubar a coleta inteira por causa disso, aqui
    a chamada é RETENTADA (com backoff) em 5xx / erro de conexão / timeout. Só
    levanta o erro se falhar em TODAS as tentativas (aí é problema de verdade).
    """
    url = f"{BASE}{endpoint}"
    ultimo_erro = None
    for i in range(max(1, tentativas)):
        try:
            resp = requests.request(metodo, url, headers=_headers(token),
                                    json=json_body, timeout=30)
            if resp.status_code >= 500:      # erro do servidor: costuma ser transitório
                ultimo_erro = requests.HTTPError(
                    f"{resp.status_code} Server Error em {endpoint}", response=resp)
                time.sleep(1.5 * (i + 1))
                continue
            resp.raise_for_status()          # 4xx = erro nosso (token/payload): não retenta
            try:
                return resp.json()
            except ValueError:
                return {"_raw": resp.text, "_status": resp.status_code}
        except (requests.ConnectionError, requests.Timeout) as e:
            ultimo_erro = e
            time.sleep(1.5 * (i + 1))
    raise ultimo_erro


# ------------------------------------------------------------------
# Setores
# ------------------------------------------------------------------
def listar_setores(token: str | None = None) -> list:
    """GET /sectors -> lista de {id, name, organizationId, ...} (setores são da
    organização, então qualquer token de canal serve)."""
    r = chamar("GET", "/core/v2/api/sectors", token=token)
    return r if isinstance(r, list) else r.get("sectors", [])


def achar_setores(*nomes: str, token: str | None = None) -> list:
    """
    Devolve os `id` dos setores cujo `name` bate (case-insensitive) com um
    dos nomes passados. Ex: achar_setores("VENDAS", "VENDAS PLANTAO").
    """
    alvo = {_normaliza(n) for n in nomes}
    return [s["id"] for s in listar_setores(token=token)
            if _normaliza(s.get("name")) in alvo]


# ------------------------------------------------------------------
# Canal do token (diagnóstico: "qual número este token enxerga")
# ------------------------------------------------------------------
def detalhe_canal(token: str | None = None) -> dict:
    """GET /channel -> o canal (número de WhatsApp) que ESTE token enxerga."""
    r = chamar("GET", "/core/v2/api/channel", token=token)
    return r if isinstance(r, dict) else {}


def nome_canal(token: str | None = None) -> str:
    """Rótulo legível do canal do token (description + número)."""
    c = detalhe_canal(token)
    desc = (c.get("description") or "").strip()
    num = (c.get("identifier") or "").strip()
    return f"{desc} ({num})".strip() if (desc or num) else "(canal desconhecido)"


# ------------------------------------------------------------------
# Atendimentos (chats)
# ------------------------------------------------------------------
def _monta_date_filters(data_inicio: str | None, data_fim: str | None) -> dict | None:
    """
    Monta o `dateFilters` (DateFiltersApiModel) filtrando pela data de INÍCIO
    do atendimento (byStartDate). Datas no formato aceito pela API (ISO).
    """
    if not data_inicio and not data_fim:
        return None
    intervalo = {}
    if data_inicio:
        intervalo["start"] = data_inicio
    if data_fim:
        intervalo["finish"] = data_fim
    return {"byStartDate": intervalo}


def listar_chats_pagina(sector_id: str | None = None,
                        status: int = STATUS_FINALIZADO,
                        tipo: int = TIPO_INDIVIDUAL,
                        data_inicio: str | None = None,
                        data_fim: str | None = None,
                        page: int = 1,
                        token: str | None = None,
                        **extra) -> dict:
    """
    POST /chats/list — UMA página (100 registros). Devolve o dict completo:
    {chats:[...], curPage, totalAmountChats, amountPage, hasNext, hasPrevius}.

    `status` e `tipo` são SEMPRE enviados (a API quebra sem eles — ver acima).
    `token` escolhe o canal (default = 1º token).
    """
    body: dict = {"page": page, "status": status, "typeChat": tipo}
    if sector_id:
        body["sectorId"] = sector_id
    df = _monta_date_filters(data_inicio, data_fim)
    if df:
        body["dateFilters"] = df
    body.update(extra)

    r = chamar("POST", "/core/v2/api/chats/list", json_body=body, token=token)
    return r if isinstance(r, dict) else {"chats": r}


def listar_chats(sector_id: str | None = None,
                 status: int | list[int] = STATUS_FINALIZADO,
                 tipo: int = TIPO_INDIVIDUAL,
                 data_inicio: str | None = None,
                 data_fim: str | None = None,
                 max_paginas: int = 100,
                 token: str | None = None,
                 **extra) -> list:
    """
    Percorre TODAS as páginas e devolve a lista completa de chats (de UM canal).

    `status` pode ser um int OU uma lista de ints (a API só aceita um status
    por chamada, então a lista é percorrida e os resultados são juntados).
    `max_paginas` é só uma trava de segurança contra loop.
    """
    statuses = status if isinstance(status, (list, tuple)) else [status]
    todos: list = []
    for st in statuses:
        page = 1
        while page <= max_paginas:
            r = listar_chats_pagina(sector_id=sector_id, status=st, tipo=tipo,
                                    data_inicio=data_inicio, data_fim=data_fim,
                                    page=page, token=token, **extra)
            chats = r.get("chats") or []
            todos.extend(chats)
            if not r.get("hasNext") or not chats:
                break
            page += 1
    return todos


def listar_chats_todos_canais(sector_id: str | None = None,
                              status: int | list[int] = STATUS_FINALIZADO,
                              tipo: int = TIPO_INDIVIDUAL,
                              data_inicio: str | None = None,
                              data_fim: str | None = None,
                              max_paginas: int = 100,
                              **extra) -> list:
    """
    Igual ao listar_chats, mas percorre TODOS os canais (todos os TOKENS) e junta.
    Cada chat volta com `_token` (o token do canal em que ele vive — necessário
    pra depois ler as mensagens dele com o token certo) e `_canal` (rótulo).
    """
    todos: list = []
    for tok in TOKENS:
        rotulo = None
        chats = listar_chats(sector_id=sector_id, status=status, tipo=tipo,
                             data_inicio=data_inicio, data_fim=data_fim,
                             max_paginas=max_paginas, token=tok, **extra)
        for c in chats:
            c["_token"] = tok
            if rotulo is None:
                rotulo = nome_canal(tok)
            c["_canal"] = rotulo
        todos.extend(chats)
    return todos


def contato_do_chat(chat: dict) -> tuple[str, str]:
    """
    Extrai (nome, numero) de um chat. O nome cai pra `description` do chat
    quando o contato não traz `name`.
    """
    c = chat.get("contact") or {}
    nome = (c.get("name") or c.get("secondaryName")
            or chat.get("description") or "").strip()
    numero = (c.get("number") or "").strip()
    return nome, numero


# ------------------------------------------------------------------
# Mensagens de um atendimento (o histórico da conversa)
# ------------------------------------------------------------------
def detalhe_chat(attendance_id: str, token: str | None = None) -> dict:
    """
    GET /chats/{attendanceId} -> dict completo do atendimento. Além dos metadados
    do chat, traz a lista `messages` com o histórico da conversa. Cada mensagem:
    {text, senderName, isSentByMe, isSystemMessage, isGpt, dhMessage, ...}.

    ⚠️ Passe o `token` do MESMO canal do chat — um token só lê os chats do seu canal.
    """
    r = chamar("GET", f"/core/v2/api/chats/{attendance_id}", token=token)
    return r if isinstance(r, dict) else {}


def mensagens_do_chat(attendance_id: str, token: str | None = None) -> list:
    """Só as mensagens do atendimento (na ordem em que aparecem na conversa)."""
    return detalhe_chat(attendance_id, token=token).get("messages") or []


# Teste rápido:  python focus_api.py            -> canais (tokens) + setores
#                python focus_api.py VENDAS      -> ids dos setores VENDAS*
if __name__ == "__main__":
    import sys
    import json

    print(f"{len(TOKENS)} canal(is) configurado(s) (FOCUS_TOKEN/FOCUS_TOKENS):")
    for i, tok in enumerate(TOKENS, 1):
        try:
            print(f"  {i}. {nome_canal(tok)}")
        except Exception as e:
            print(f"  {i}. (erro ao ler canal: {e})")
    print()

    if len(sys.argv) > 1:
        print("IDs encontrados:", achar_setores(*sys.argv[1:]))
    else:
        setores = listar_setores()
        print(f"{len(setores)} setores:")
        for s in setores:
            print(f"  {s.get('id')}  ->  {s.get('name')}")
