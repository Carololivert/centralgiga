"""Configuração do worker: carrega o .env e cria o client Supabase (service_role)."""
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from supabase import Client, create_client

TZ_BR = ZoneInfo("America/Sao_Paulo")


def _bool_env(nome: str, padrao: str = "true") -> bool:
    return os.environ.get(nome, padrao).strip().lower() not in ("0", "false", "no", "off")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
RESULT_BUCKET = os.environ.get("RESULT_BUCKET", "resultados").strip()
POLL_SECONDS = float(os.environ.get("WORKER_POLL_SECONDS", "5"))

# ── Monitor SmartOLT (API HTTP embarcada no worker; ver monitor/service.py) ──
MONITOR_ENABLED = _bool_env("MONITOR_API_ENABLED")
MONITOR_HOST = os.environ.get("MONITOR_HOST", "127.0.0.1").strip()
MONITOR_PORT = int(os.environ.get("MONITOR_PORT", "5001"))

# ── Agenda: sincronização diária da Produção (ver agenda.py) ──
# Roda às 18h de Brasília — horário em que o técnico encerra o expediente — e
# re-lê os últimos dias para pegar OS finalizadas fora do horário.
PRODUCAO_SYNC_ENABLED = _bool_env("PRODUCAO_SYNC_ENABLED")
PRODUCAO_SYNC_HORA = os.environ.get("PRODUCAO_SYNC_HORA", "18:00").strip()
PRODUCAO_SYNC_DIAS = int(os.environ.get("PRODUCAO_SYNC_DIAS", "3"))


def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no worker/.env "
            "(a service_role key fica SÓ aqui, nunca no frontend)."
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
