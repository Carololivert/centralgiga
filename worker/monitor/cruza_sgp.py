#!/usr/bin/env python3
"""
cruza_sgp.py — Cruza uma ONU da SmartOLT com o cliente no SGP.

Regra de conferência (definida pela equipe), em CASCATA — para no 1º que achar:
    1) name    (OLT) == login (SGP)
    2) name    (OLT) == nome  (SGP)
    3) address (OLT) == login (SGP)      (address = "address or comment")
    4) address (OLT) == nome  (SGP)

Realidade dos dados (ver monitor/DESIGN.md §9):
  - O campo `name` da OLT costuma ser o LOGIN (~89% — ex.: "maria.rocha172").
    Por isso o passo 1 sozinho resolve a maioria.
  - Busca no SGP por LOGIN é rápida (~1s) e exata (1 cliente) → passos 1 e 3.
  - ⚠️ Busca por NOME NÃO funciona nesta API: `/api/ura/clientes/` IGNORA o filtro
    `nome` e devolve os 100 primeiros em ordem alfabética (~35s). Logo os passos 2 e 4
    (por nome) NÃO são automatizáveis hoje (só na tela do SGP). `deep=True` fica como
    placeholder — só resolve se o cliente cair por acaso nos 100 alfabéticos.

Uso:
    python monitor/cruza_sgp.py                    # resolve ONUs caídas (cascata rápida)
    python monitor/cruza_sgp.py maria.rocha172     # resolve um valor (login/nome)
    python monitor/cruza_sgp.py --deep <valor>     # inclui os passos por nome (lento)
"""

import os
import re
import sys
import time
import unicodedata
from collections import Counter

import requests
# Pacote do worker: o .env (com SGP_TOKEN/SGP_APP) é carregado pelo worker/config.py.
from . import sgp_api

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_cache_login: dict[str, dict | None] = {}
_cache_nome: dict[str, dict | None] = {}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split())


def _usavel_como_login(v) -> str | None:
    """Login não tem espaço. Ex.: 'maria.rocha172', 'joao_silva'."""
    s = (v or "").strip()
    return s if s and " " not in s and len(s) >= 3 and re.fullmatch(r"[\w.\-@]+", s) else None


def _fmt_endereco(end: dict | None) -> str:
    if not isinstance(end, dict):
        return ""
    logr = (end.get("logradouro") or "").strip()
    num = end.get("numero")
    p1 = logr + (f", {num}" if num not in (None, "", 0) else "")
    partes = [x for x in (p1, (end.get("bairro") or "").strip(),
                          f"{end.get('cidade','')}/{end.get('uf','')}".strip("/"),
                          (end.get("cep") or "").strip()) if x]
    return " - ".join(partes)


def _servico_do_login(cliente: dict, login: str) -> tuple[dict, dict]:
    alvo = (login or "").lower()
    for contrato in cliente.get("contratos") or []:
        for serv in contrato.get("servicos") or []:
            if (serv.get("login") or "").lower() == alvo:
                return contrato, serv
    contratos = cliente.get("contratos") or []
    return (contratos[0] if contratos else {}), {}


def _achatar(cliente: dict, login_ref: str | None, via: str) -> dict:
    contrato, serv = _servico_do_login(cliente, login_ref or "")
    contatos = cliente.get("contatos") or {}
    return {
        "nome": cliente.get("nome"),
        "cpfcnpj": cliente.get("cpfcnpj"),
        "endereco": _fmt_endereco(contrato.get("endereco") or cliente.get("endereco")),
        "contrato_id": contrato.get("id"),
        "contrato_status": contrato.get("status"),
        "plano": (serv.get("plano") or {}).get("descricao"),
        "telefones": (contatos.get("celulares") or []) + (contatos.get("telefones") or []),
        "via": via,
    }


def _por_login(valor: str) -> dict | None:
    login = _usavel_como_login(valor)
    if not login:
        return None
    if login in _cache_login:
        c = _cache_login[login]
        return _achatar(c, login, "login") if c else None
    try:
        clientes = sgp_api.consultar_cliente(login, campo="login")
    except Exception:
        return None
    c = clientes[0] if clientes else None
    _cache_login[login] = c
    return _achatar(c, login, "login") if c else None


def _por_nome_exato(valor: str, timeout: int = 60) -> dict | None:
    """Passo lento: busca por nome (até 100) e filtra o nome EXATO (normalizado)."""
    alvo = _norm(valor)
    if len(alvo) < 5:
        return None
    if alvo in _cache_nome:
        c = _cache_nome[alvo]
        return _achatar(c, None, "nome") if c else None
    body = {"token": sgp_api.TOKEN, "app": sgp_api.APP, "nome": valor}
    try:
        r = requests.post(sgp_api.BASE + sgp_api.ENDPOINT_CLIENTE, data=body,
                          verify=sgp_api.VERIFY_SSL, timeout=timeout)
        j = r.json()
        clientes = j.get("clientes", []) if isinstance(j, dict) else (j or [])
    except Exception:
        return None
    achado = next((c for c in clientes if _norm(c.get("nome")) == alvo), None)
    _cache_nome[alvo] = achado
    return _achatar(achado, None, "nome") if achado else None


def resolver_onu(onu: dict, deep: bool = False) -> dict:
    """
    Aplica a cascata name→address (login→nome) e devolve um dict unificado com
    dados da ONU + cliente do SGP (quando achar). `deep=True` inclui os passos
    por nome (lentos). Campo `via` diz qual passo casou.
    """
    name = (onu.get("name") or "").strip()
    addr = (onu.get("address") or "").strip()
    base = {
        "onu_sn": onu.get("sn") or onu.get("unique_external_id"),
        "onu_status": onu.get("status"),
        "caiu_em": onu.get("last_status_change"),
        "olt_id": onu.get("olt_id"), "board": onu.get("board"),
        "port": onu.get("port"), "onu": onu.get("onu"),
        "name_olt": name, "address_olt": addr,
        "nome": name or None, "cpfcnpj": None, "endereco": None,
        "contrato_id": None, "contrato_status": None, "plano": None,
        "telefones": [], "via": None, "fonte": "smartolt",
    }
    # cascata: 1) name=login  2) name=nome  3) address=login  4) address=nome
    achado = _por_login(name)
    if not achado and deep:
        achado = _por_nome_exato(name)
    if not achado:
        achado = _por_login(addr)
    if not achado and deep:
        achado = _por_nome_exato(addr)

    if achado:
        base.update({k: achado[k] for k in
                     ("nome", "cpfcnpj", "endereco", "contrato_id",
                      "contrato_status", "plano", "telefones", "via")})
        base["fonte"] = "sgp"
    return base


def resolver_varios(onus: list[dict], deep: bool = False) -> list[dict]:
    return [resolver_onu(o, deep=deep) for o in onus]


# ------------------------------------------------------------------
def _demo_caidos(limite=12, deep=False):
    import smartolt_api
    recs = smartolt_api.status_onus() or []
    caidos = [r for r in recs if r.get("status") in ("LOS", "Offline", "Power fail")]
    print(f"{len(caidos)} ONU(s) caída(s) de {len(recs)}. Resolvendo até {limite} "
          f"(deep={deep})...\n")
    t0 = time.time()
    achou = Counter()
    for onu in caidos[:limite]:
        r = resolver_onu(onu, deep=deep)
        achou[r["via"] or "nao-achou"] += 1
        marca = f"✔ {r['contrato_status']}" if r["fonte"] == "sgp" else "~ só-OLT"
        print(f"● {r['nome']}  [{r['onu_status']}]  ({marca}, via {r['via']})")
        print(f"    OLT {r['olt_id']} b{r['board']}/p{r['port']} · contrato {r['contrato_id']}")
        print(f"    {r['endereco'] or '(sem endereço)'} · {r['plano'] or ''}")
        print(f"    tel: {', '.join(r['telefones']) or '-'}\n")
    print(f"resumo: {dict(achou)}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    from collections import Counter
    args = [a for a in sys.argv[1:] if a != "--deep"]
    deep = "--deep" in sys.argv
    if args:
        import json
        onu = {"name": args[0], "address": ""}
        print(json.dumps(resolver_onu(onu, deep=deep), ensure_ascii=False, indent=2))
    else:
        _demo_caidos(deep=deep)
