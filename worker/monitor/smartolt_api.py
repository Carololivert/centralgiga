"""
smartolt_api.py — Cliente da API oficial da SmartOLT (gestão de OLT/ONU FTTH).

Autenticação: header `X-Token` = API key gerada no painel da SmartOLT
(Settings → API). NÃO usa login/2FA — é só o token.

.env (na raiz):
    SMARTOLT_SUBDOMAIN=giganet      # o "xxxxx" de https://xxxxx.smartolt.com
    SMARTOLT_TOKEN=xxxxxxxxxxxxxxxx  # a API key

Referência de endpoints: comum/API_SMARTOLT.md
Dependências:
    pip install requests python-dotenv

Uso rápido (teste de conexão):
    python comum/smartolt_api.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUBDOMAIN = os.getenv("SMARTOLT_SUBDOMAIN", "").strip()
TOKEN = os.getenv("SMARTOLT_TOKEN", "").strip()
# Permite sobrescrever a base inteira se algum dia mudar o padrão de URL.
BASE = os.getenv("SMARTOLT_BASE", f"https://{SUBDOMAIN}.smartolt.com").rstrip("/")
TIMEOUT = int(os.getenv("SMARTOLT_TIMEOUT", "30"))


class SmartOLTError(RuntimeError):
    """Erro devolvido pela API (status=false) ou de autenticação."""


def _headers() -> dict:
    if not TOKEN:
        raise SmartOLTError("Falta SMARTOLT_TOKEN no .env (API key da SmartOLT).")
    if not SUBDOMAIN and "SMARTOLT_BASE" not in os.environ:
        raise SmartOLTError("Falta SMARTOLT_SUBDOMAIN no .env (o 'xxx' de xxx.smartolt.com).")
    return {"X-Token": TOKEN}


def chamar(metodo: str, endpoint: str, **kwargs):
    """
    Chamador genérico. Injeta o header X-Token.
    Ex: chamar("GET", "/api/system/get_olts")

    A SmartOLT responde {"status": true, "response": ...} em caso de sucesso
    e {"status": false, "error_code": .., "response": "<msg>"} em caso de erro.
    Devolve o JSON cru (sem desembrulhar) — use `dados()` para pegar o miolo.
    """
    url = f"{BASE}{endpoint}"
    resp = requests.request(metodo, url, headers=_headers(), timeout=TIMEOUT, **kwargs)
    # 401/403 = token inválido / sem permissão; mostra mensagem clara.
    if resp.status_code in (401, 403):
        raise SmartOLTError(
            f"Autenticação recusada (HTTP {resp.status_code}). "
            f"Confira SMARTOLT_TOKEN e se a API está liberada para este subdomínio."
        )
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        return {"_raw": resp.text, "_status": resp.status_code}


def dados(resp):
    """
    Desembrulha a resposta padrão da SmartOLT. Devolve `response` quando
    status=true; levanta SmartOLTError com a mensagem quando status=false.
    """
    if isinstance(resp, dict) and "status" in resp:
        if resp.get("status"):
            return resp.get("response")
        raise SmartOLTError(resp.get("response") or f"erro (code {resp.get('error_code')})")
    return resp


def get(endpoint: str):
    """GET + desembrulho num passo só."""
    return dados(chamar("GET", endpoint))


# ------------------------------------------------------------------
# Atalhos das métricas que o monitor usa
# ------------------------------------------------------------------
def listar_olts() -> list:
    """Lista as OLTs (nome, IP, portas, olt_id único)."""
    return get("/api/system/get_olts") or []


def temperatura_olts():
    """Uptime + temperatura ambiente de cada OLT."""
    return get("/api/olt/get_olts_uptime_and_env_temperature")


def status_onus():
    """Status de todas as ONUs (inclui LOS = Loss of Signal / offline)."""
    return get("/api/onu/get_onus_statuses")


def pons_em_outage(olt_id):
    """Portas PON inteiras em queda (outage) de uma OLT."""
    return get(f"/api/system/get_outage_pons/{olt_id}")


def sinais_onus():
    """Sinal (RX/TX) de todas as ONUs — para detectar sinal fraco."""
    return get("/api/onu/get_onus_signals")


# ------------------------------------------------------------------
# Teste de conexão:  python comum/smartolt_api.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    import json
    import sys

    print(f"Base: {BASE}")
    print(f"Token: {'<definido>' if TOKEN else '<VAZIO>'}\n")
    try:
        olts = listar_olts()
    except SmartOLTError as e:
        print(f"[FALHOU] {e}")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"[FALHOU] Erro de rede: {e}")
        sys.exit(1)

    print(f"[OK] Conectado! {len(olts)} OLT(s) encontrada(s):")
    for o in olts:
        nome = o.get("name") or o.get("olt_name") or "?"
        oid = o.get("id") or o.get("olt_id") or "?"
        ip = o.get("ip") or o.get("olt_ip") or ""
        print(f"  - {nome}  (id={oid})  {ip}")
    if olts:
        print("\nExemplo de OLT (campos disponíveis):")
        print(json.dumps(olts[0], indent=2, ensure_ascii=False))
