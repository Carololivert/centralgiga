"""Agenda do worker: a rotina que roda sozinha, sem ninguém clicar.

Hoje só tem uma tarefa — **sincronizar a Produção às 18h** (horário em que o
técnico encerra o expediente), que alimenta o dashboard /producao da Central.

Roda numa thread ao lado da fila de jobs: nunca bloqueia o worker, e uma falha
aqui não derruba o processamento das automações.

Como decide a hora (sem depender de cron do sistema operacional):
  • acorda de minuto em minuto e compara com o horário configurado, no fuso de
    **Brasília** — o container pode estar em UTC;
  • guarda o dia da última execução, então roda **uma vez por dia**;
  • se o worker estava fora do ar às 18h e sobe às 20h, a checagem de arranque
    (em `os_sync`) percebe que o dia ainda não foi sincronizado e roda na hora —
    um deploy no meio da tarde não deixa buraco no dashboard;
  • se o SGP estiver fora do ar na hora, tenta de novo em 15 min (até 4 vezes)
    antes de desistir do dia — um soluço às 18h não custa o relatório inteiro.
"""
import sys
import threading
import time
import traceback
from datetime import date, datetime, time as dtime, timedelta

from automacoes.producao_os import sincronizar_janela
from config import (
    PRODUCAO_SYNC_DIAS, PRODUCAO_SYNC_ENABLED, PRODUCAO_SYNC_HORA,
    TZ_BR, get_client,
)

INTERVALO_CHECAGEM = 60   # segundos entre uma checagem de relógio e outra
MAX_TENTATIVAS = 4        # por dia, quando a sincronização falha
ESPERA_RETENTATIVA = 15   # minutos entre as tentativas


def _p(msg) -> None:
    """Escreve no console REAL (sys.__stdout__), igual ao _p() do worker.py.

    Um `print()` comum resolveria sys.stdout na hora da chamada — e vários
    adapters trocam o sys.stdout GLOBAL do processo por um redirect_stdout para
    capturar a saída do script. Como a agenda roda numa thread ao lado, um
    "[agenda] sincronizando…" caindo às 18h no meio de um job de outra pessoa
    seria gravado no job_logs DAQUELE job, e apareceria na tela dela."""
    try:
        saida = sys.__stdout__ or sys.stdout
        saida.write(f"[agenda] {msg}\n")
        saida.flush()
    except Exception:
        pass


def _parse_hora(texto: str) -> dtime:
    """'18:00' -> time(18, 0). Valor estranho cai no padrão 18:00."""
    try:
        h, m = (texto or "").strip().split(":")
        return dtime(int(h), int(m))
    except (ValueError, AttributeError):
        _p(f"PRODUCAO_SYNC_HORA inválida ({texto!r}); usando 18:00.")
        return dtime(18, 0)


def _ultimo_dia_sincronizado(client) -> date | None:
    """Dia (Brasília) da última sincronização automática que deu CERTO.

    Serve para o worker que sobe depois das 18h saber se o dia já foi coberto.
    Se a consulta falhar, devolve None — o pior caso é uma sincronização a mais,
    que é idempotente (upsert por os_id).
    """
    try:
        r = (client.table("os_sync")
             .select("criado_em")
             .eq("origem", "agenda").eq("ok", True)
             .order("criado_em", desc=True).limit(1).execute())
        if not r.data:
            return None
        quando = datetime.fromisoformat(str(r.data[0]["criado_em"]).replace("Z", "+00:00"))
        return quando.astimezone(TZ_BR).date()
    except Exception as e:
        _p(f"[warn] não consegui ler a última sincronização: {e}")
        return None


def _rodar(client, horario: dtime) -> None:
    _p(f"sincronizando a produção (janela de {PRODUCAO_SYNC_DIAS} dia(s))…")
    resultado = sincronizar_janela(
        client, dias_atras=PRODUCAO_SYNC_DIAS, origem="agenda", log=lambda m: _p(f"  {m}")
    )
    _p(f"produção atualizada: {resultado['gravados']} OS gravadas "
       f"(rotina das {horario:%H:%M}).")


def _loop() -> None:
    horario = _parse_hora(PRODUCAO_SYNC_HORA)

    client = None
    ultimo_dia: date | None = None     # dia já resolvido (sucesso ou desistência)
    dia_tentativas: date | None = None  # a que dia o contador abaixo se refere
    tentativas = 0
    proxima_tentativa: datetime | None = None

    while True:
        try:
            # Conexão preguiçosa: se o Supabase estiver fora no arranque, a thread
            # não morre — tenta de novo no próximo minuto.
            if client is None:
                client = get_client()
                ultimo_dia = _ultimo_dia_sincronizado(client)
                _p(f"produção agendada para {horario:%H:%M} (Brasília) · última execução: "
                   f"{ultimo_dia.strftime('%d/%m/%Y') if ultimo_dia else 'nenhuma'}")

            agora = datetime.now(TZ_BR)
            hoje = agora.date()

            if dia_tentativas != hoje:  # virou o dia: zera o contador
                dia_tentativas, tentativas, proxima_tentativa = hoje, 0, None

            na_hora = agora.time() >= horario
            pode_tentar = proxima_tentativa is None or agora >= proxima_tentativa

            if ultimo_dia != hoje and na_hora and pode_tentar:
                try:
                    _rodar(client, horario)
                    ultimo_dia = hoje
                    tentativas, proxima_tentativa = 0, None
                except Exception as e:
                    tentativas += 1
                    if tentativas >= MAX_TENTATIVAS:
                        # Desiste do dia para não ficar batendo no SGP de minuto
                        # em minuto. O erro já ficou registrado em os_sync, e o
                        # painel avisa que os dados estão velhos.
                        ultimo_dia = hoje
                        _p(f"[erro] desisti hoje após {tentativas} tentativa(s): {e}")
                    else:
                        proxima_tentativa = agora + timedelta(minutes=ESPERA_RETENTATIVA)
                        _p(f"[erro] tentativa {tentativas}/{MAX_TENTATIVAS} falhou ({e}); "
                           f"tento de novo às {proxima_tentativa:%H:%M}.")
        except Exception as e:
            _p(f"[erro] a agenda tropeçou: {e}")
            traceback.print_exc()
            client = None  # força recriar o client na próxima volta

        time.sleep(INTERVALO_CHECAGEM)


def iniciar_em_thread() -> None:
    """Sobe a agenda em background. Desligar: PRODUCAO_SYNC_ENABLED=false."""
    if not PRODUCAO_SYNC_ENABLED:
        _p("desligada (PRODUCAO_SYNC_ENABLED=false).")
        return
    threading.Thread(target=_loop, name="agenda", daemon=True).start()


if __name__ == "__main__":
    # Teste avulso: python -m agenda  (roda a sincronização na hora e sai)
    _rodar(get_client(), _parse_hora(PRODUCAO_SYNC_HORA))
