"""Worker da Central Giganet.

Loop: reivindica o próximo job da fila (RPC claim_next_job), executa a
automação correspondente, grava logs ao vivo em job_logs, sobe o resultado
no Storage e marca o job como concluido/erro.

Usa a service_role key (ignora RLS) — rode onde for seguro (seu PC ou um VPS).
"""
import sys
import time
import traceback
from datetime import datetime, timezone

from automacoes.base import Resultado
from automacoes.registry import REGISTRY, get_automacao
from config import (
    POLL_SECONDS, RESULT_BUCKET, get_client,
    MONITOR_ENABLED, MONITOR_HOST, MONITOR_PORT,
)


def _setup_console():
    """Força UTF-8 (Windows usa cp1252 e quebra com '✓'/emojis)."""
    for stream in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _p(msg) -> None:
    """Escreve no console REAL (sys.__stdout__), imune ao redirect_stdout que os
    adapters usam para capturar a saída dos scripts — senão vira loop de logging."""
    try:
        out = sys.__stdout__ or sys.stdout
        out.write(str(msg) + "\n")
        out.flush()
    except Exception:
        pass


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def reivindicar(client):
    """Chama claim_next_job(); retorna o job (dict) ou None."""
    res = client.rpc("claim_next_job").execute()
    data = res.data
    if not data:
        return None
    if isinstance(data, list):
        return data[0] if data else None
    return data


def log_factory(client, job_id: str):
    def log(linha, nivel: str = "info"):
        linha = str(linha)
        _p(f"  [{job_id[:8]}] {linha}")
        try:
            client.table("job_logs").insert(
                {"job_id": job_id, "level": nivel, "line": linha[:4000]}
            ).execute()
        except Exception as e:  # nunca derruba o job por falha de log
            _p(f"  [warn] falha ao gravar log: {e}")

    return log


def subir_arquivos(client, job_id: str, resultado: Resultado, log) -> str | None:
    result_path = None
    for arq in resultado.arquivos:
        path = f"{job_id}/{arq.nome}"
        client.storage.from_(RESULT_BUCKET).upload(
            path,
            arq.conteudo,
            {"content-type": arq.content_type, "upsert": "true"},
        )
        log(f"Resultado salvo no Storage: {arq.nome}")
        if result_path is None:
            result_path = path
    return result_path


def marcar_concluido(client, job_id: str, result_path, preview):
    client.table("jobs").update(
        {
            "status": "concluido",
            "result_path": result_path,
            "result_preview": preview or None,
            "error": None,
            "finished_at": agora_iso(),
        }
    ).eq("id", job_id).execute()


def auditar(client, job: dict, status: str, detalhe) -> None:
    """Registra a execução de um sistema auditável (ex. ação destrutiva) no audit_log."""
    try:
        client.table("audit_log").insert(
            {
                "user_id": job.get("requested_by"),
                "action": job.get("system_slug"),
                "detail": {
                    "status": status,
                    "params": job.get("params") or {},
                    "resumo": (str(detalhe) if detalhe else "")[:500],
                },
            }
        ).execute()
    except Exception as e:
        _p(f"  [warn] falha ao auditar: {e}")


def marcar_erro(client, job_id: str, mensagem: str):
    client.table("jobs").update(
        {
            "status": "erro",
            "error": (mensagem or "erro desconhecido")[:4000],
            "finished_at": agora_iso(),
        }
    ).eq("id", job_id).execute()


def processar(client, job: dict):
    job_id = job["id"]
    slug = job["system_slug"]
    params = job.get("params") or {}
    log = log_factory(client, job_id)
    _p(f"[worker] job {job_id} · {slug}")

    automacao = get_automacao(slug)
    if automacao is None:
        marcar_erro(client, job_id, f"Sem automação registrada para '{slug}'.")
        return

    auditavel = getattr(automacao, "auditavel", False)
    try:
        resultado = automacao.run(params, log) or Resultado()
        result_path = subir_arquivos(client, job_id, resultado, log)
        marcar_concluido(client, job_id, result_path, resultado.preview)
        if auditavel:
            auditar(client, job, "concluido", resultado.preview)
        log("Concluído ✓")
    except Exception as e:
        log(f"Falhou: {e}", "error")
        marcar_erro(client, job_id, str(e))
        if auditavel:
            auditar(client, job, "erro", str(e))


def iniciar_monitor():
    """Sobe a API do Monitor SmartOLT numa thread (não bloqueia a fila).
    Falha aqui é só um aviso — o processamento de jobs continua normal."""
    if not MONITOR_ENABLED:
        return
    try:
        from monitor.service import iniciar_em_thread
        iniciar_em_thread(MONITOR_HOST, MONITOR_PORT)
        _p(f"[worker] monitor SmartOLT em http://{MONITOR_HOST}:{MONITOR_PORT} (API p/ a Central)")
    except Exception as e:
        _p(f"[worker] [warn] monitor não subiu: {e} (a fila de jobs segue normal)")


def main():
    _setup_console()
    client = get_client()
    _p(f"[worker] iniciado · bucket={RESULT_BUCKET} · poll={POLL_SECONDS}s")
    _p(f"[worker] automações: {', '.join(REGISTRY) or '(nenhuma)'}")
    iniciar_monitor()

    while True:
        try:
            job = reivindicar(client)
            if not job:
                time.sleep(POLL_SECONDS)
                continue
            processar(client, job)
        except KeyboardInterrupt:
            _p("\n[worker] encerrando…")
            break
        except Exception as e:
            _p(f"[worker] erro no loop: {e}")
            traceback.print_exc()
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
