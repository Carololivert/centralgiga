"""Configuração do worker: carrega o .env e cria o client Supabase (service_role)."""
import os

from dotenv import load_dotenv
from supabase import Client, create_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
RESULT_BUCKET = os.environ.get("RESULT_BUCKET", "resultados").strip()
POLL_SECONDS = float(os.environ.get("WORKER_POLL_SECONDS", "5"))


def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no worker/.env "
            "(a service_role key fica SÓ aqui, nunca no frontend)."
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
