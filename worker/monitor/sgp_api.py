"""
sgp_api.py - Cliente da API publica do SGP (Token/App). OS via URA (sem 2FA).
"""
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("SGP_BASE", "https://giganetwireless.sgp.net.br").rstrip("/")
TOKEN = os.getenv("SGP_TOKEN")
APP = os.getenv("SGP_APP")
VERIFY_SSL = os.getenv("SGP_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}

ENDPOINT_CLIENTE = "/api/ura/clientes/"
ENDPOINT_OS_LIST = "/api/ura/ordemservico/list/"

if not VERIFY_SSL:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def chamar(endpoint, **campos):
    if not TOKEN or not APP:
        raise RuntimeError("Faltam SGP_TOKEN / SGP_APP no .env")
    url = f"{BASE}{endpoint}"
    body = {"token": TOKEN, "app": APP, **campos}
    resp = requests.post(url, data=body, verify=VERIFY_SSL, timeout=30)
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        return {"_raw": resp.text, "_status": resp.status_code}


def _variacoes_telefone(numero):
    d = re.sub(r"\D", "", numero)
    if d.startswith("55") and len(d) > 11:
        d = d[2:]
    variantes = {d}
    if len(d) == 11 and d[2] == "9":
        variantes.add(d[:2] + d[3:])
    elif len(d) == 10:
        variantes.add(d[:2] + "9" + d[2:])
    return list(variantes)


def _extrair_clientes(resp):
    if isinstance(resp, dict):
        return resp.get("clientes", [])
    if isinstance(resp, list):
        return resp
    return []


def consultar_cliente(termo, campo="telefone"):
    if campo == "telefone":
        for var in _variacoes_telefone(termo):
            clientes = _extrair_clientes(chamar(ENDPOINT_CLIENTE, telefone=var))
            if clientes:
                return clientes
        return []
    return _extrair_clientes(chamar(ENDPOINT_CLIENTE, **{campo: termo}))


def eh_cliente(numero):
    return bool(consultar_cliente(numero, campo="telefone"))


def listar_os(data_agendamento_inicio=None, data_agendamento_fim=None,
              data_finalizacao_inicio=None, data_finalizacao_fim=None,
              status=None, limit=1000, offset=0, **extra):
    campos = {"limit": limit, "offset": offset}
    if data_agendamento_inicio:
        campos["data_agendamento_inicio"] = data_agendamento_inicio
    if data_agendamento_fim:
        campos["data_agendamento_fim"] = data_agendamento_fim
    if data_finalizacao_inicio:
        campos["data_finalizacao_inicio"] = data_finalizacao_inicio
    if data_finalizacao_fim:
        campos["data_finalizacao_fim"] = data_finalizacao_fim
    if status is not None:
        campos["status"] = status
    campos.update(extra)
    r = chamar(ENDPOINT_OS_LIST, **campos)
    if isinstance(r, dict):
        return r.get("ordens_servicos") or r.get("ordens") or r.get("os") or []
    if isinstance(r, list):
        return r
    return []


if __name__ == "__main__":
    import sys, json
    termo = sys.argv[1] if len(sys.argv) > 1 else input("Numero/termo: ")
    print(json.dumps(consultar_cliente(termo), indent=2, ensure_ascii=False))
