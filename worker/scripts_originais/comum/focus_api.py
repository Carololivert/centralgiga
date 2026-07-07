"""
focus_api.py — Cliente da API oficial do FocusChat.

Por que a API: o `vendas` puxava atendimentos raspando a lista virtualizada
do painel (Playwright), que travava e só pegava ~15 de ~100. A API oficial
devolve NOME + NÚMERO prontos em cada chat, paginado, sem raspar nada.

Autenticação: header `access-token` = Token do Canal (gerado no FocusChat).
.env (na raiz):
    FOCUS_TOKEN=xxxxxxxxxxxxxxxxxxxx

Referência: https://api.focuschat.com.br/swagger/index.html
Dependências:
    pip install requests python-dotenv
"""

import os
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
TOKEN = os.getenv("FOCUS_TOKEN")

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


def _headers() -> dict:
    if not TOKEN:
        raise RuntimeError("Falta FOCUS_TOKEN no .env (Token do Canal do FocusChat)")
    return {"access-token": TOKEN, "Content-Type": "application/json"}


def chamar(metodo: str, endpoint: str, json_body: dict | None = None) -> dict | list:
    """
    Chamador genérico da API do FocusChat (injeta o access-token).
    Ex: chamar("GET", "/core/v2/api/sectors")
    """
    url = f"{BASE}{endpoint}"
    resp = requests.request(metodo, url, headers=_headers(),
                            json=json_body, timeout=30)
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        return {"_raw": resp.text, "_status": resp.status_code}


# ------------------------------------------------------------------
# Setores
# ------------------------------------------------------------------
def listar_setores() -> list:
    """GET /sectors -> lista de {id, name, organizationId, ...}."""
    r = chamar("GET", "/core/v2/api/sectors")
    return r if isinstance(r, list) else r.get("sectors", [])


def achar_setores(*nomes: str) -> list:
    """
    Devolve os `id` dos setores cujo `name` bate (case-insensitive) com um
    dos nomes passados. Ex: achar_setores("VENDAS", "VENDAS PLANTAO").
    """
    alvo = {_normaliza(n) for n in nomes}
    return [s["id"] for s in listar_setores()
            if _normaliza(s.get("name")) in alvo]


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
                        **extra) -> dict:
    """
    POST /chats/list — UMA página (100 registros). Devolve o dict completo:
    {chats:[...], curPage, totalAmountChats, amountPage, hasNext, hasPrevius}.

    `status` e `tipo` são SEMPRE enviados (a API quebra sem eles — ver acima).
    """
    body: dict = {"page": page, "status": status, "typeChat": tipo}
    if sector_id:
        body["sectorId"] = sector_id
    df = _monta_date_filters(data_inicio, data_fim)
    if df:
        body["dateFilters"] = df
    body.update(extra)

    r = chamar("POST", "/core/v2/api/chats/list", json_body=body)
    return r if isinstance(r, dict) else {"chats": r}


def listar_chats(sector_id: str | None = None,
                 status: int | list[int] = STATUS_FINALIZADO,
                 tipo: int = TIPO_INDIVIDUAL,
                 data_inicio: str | None = None,
                 data_fim: str | None = None,
                 max_paginas: int = 100,
                 **extra) -> list:
    """
    Percorre TODAS as páginas e devolve a lista completa de chats.

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
                                    page=page, **extra)
            chats = r.get("chats") or []
            todos.extend(chats)
            if not r.get("hasNext") or not chats:
                break
            page += 1
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


# Teste rápido:  python focus_api.py            -> lista os setores
#                python focus_api.py VENDAS      -> ids dos setores VENDAS*
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) > 1:
        print("IDs encontrados:", achar_setores(*sys.argv[1:]))
    else:
        setores = listar_setores()
        print(f"{len(setores)} setores:")
        for s in setores:
            print(f"  {s.get('id')}  ->  {s.get('name')}")
        print()
        print(json.dumps(setores[:1], indent=2, ensure_ascii=False))
