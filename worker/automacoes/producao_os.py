"""Sincronização da Produção: SGP → tabela `os_producao` (dashboard /producao).

Duas portas de entrada, um caminho só (`sincronizar`):

  • automática — `worker/agenda.py` chama todo dia às 18h (hora em que o técnico
    encerra o expediente), re-lendo também os últimos dias;
  • manual — a automação **producao-sync** na Central, para carregar meses
    anteriores (backfill) ou reprocessar um dia específico.

Idempotente: o upsert usa `os_id` como chave, então rodar o mesmo período de
novo só ATUALIZA as linhas. É assim que a OS lançada às 19h30 (depois da
sincronização das 18h) entra na próxima passada, sem duplicar nada.

Só LÊ o SGP — nada é alterado lá.
"""
import csv
import io
import os
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .base import Arquivo, BaseAutomacao, Resultado
from .runner import carregar_script

TZ_BR = ZoneInfo("America/Sao_Paulo")

# Quantas linhas por requisição ao PostgREST. 500 mantém o corpo do POST em
# alguns MB — um mês inteiro (~1.200 OS) sai em 3 idas.
LOTE = 500

# Colunas do CSV anexo (o detalhe que não cabe no texto da tela).
CAMPOS_CSV = [
    "os_id", "data_finalizacao", "hora_finalizacao", "categoria", "subcategoria",
    "motivo", "pop", "pop_num", "pop_regiao", "equipe", "cliente", "contrato",
    "contrato_status", "usuario_finalizacao", "data_cadastro", "espera_dias",
]


def hoje_br() -> date:
    """Hoje no fuso de Brasília — o worker pode rodar num VPS em UTC."""
    return datetime.now(TZ_BR).date()


def _registrar_sync(client, **campos) -> None:
    """Grava a passada em os_sync (o painel mostra 'atualizado às …').
    Falha de log NUNCA derruba a sincronização."""
    try:
        client.table("os_sync").insert(campos).execute()
    except Exception:
        pass


def sincronizar(client, de: date, ate: date, origem: str = "manual", log=print) -> dict:
    """Lê as OS finalizadas entre `de` e `ate` no SGP e grava em os_producao.

    `client` é o Supabase com service_role (RLS não se aplica — é o único que
    escreve nessas tabelas). Devolve {'total', 'gravados', 'linhas'}.
    """
    P = carregar_script("relatorios/producao_os.py")
    inicio = time.monotonic()

    try:
        linhas = P.coletar(de, ate, log=log)
    except Exception as e:
        _registrar_sync(client, origem=origem, de=de.isoformat(), ate=ate.isoformat(),
                        total=0, gravados=0, ok=False, erro=str(e)[:2000],
                        duracao_ms=int((time.monotonic() - inicio) * 1000))
        raise

    # Uma OS só pode aparecer uma vez por lote: o Postgres recusa um ON CONFLICT
    # que tenta afetar a mesma linha duas vezes (erro 21000). Hoje a paginação do
    # SGP não repete, mas isso é contrato da API, não garantia nossa — e a última
    # ocorrência é a mais recente, então é ela que fica.
    unicas = {l["os_id"]: l for l in linhas}
    if len(unicas) != len(linhas):
        log(f"⚠️ {len(linhas) - len(unicas)} OS repetida(s) na resposta do SGP — mantive a última de cada.")
    linhas = list(unicas.values())

    agora = datetime.now(timezone.utc).isoformat()
    gravados = 0
    try:
        for i in range(0, len(linhas), LOTE):
            lote = [{**l, "atualizado_em": agora} for l in linhas[i:i + LOTE]]
            client.table("os_producao").upsert(lote, on_conflict="os_id").execute()
            gravados += len(lote)
            log(f"  gravadas {gravados}/{len(linhas)} no banco")
    except Exception as e:
        _registrar_sync(client, origem=origem, de=de.isoformat(), ate=ate.isoformat(),
                        total=len(linhas), gravados=gravados, ok=False, erro=str(e)[:2000],
                        duracao_ms=int((time.monotonic() - inicio) * 1000))
        raise

    _registrar_sync(client, origem=origem, de=de.isoformat(), ate=ate.isoformat(),
                    total=len(linhas), gravados=gravados, ok=True,
                    duracao_ms=int((time.monotonic() - inicio) * 1000))
    return {"total": len(linhas), "gravados": gravados, "linhas": linhas}


def sincronizar_janela(client, dias_atras: int = 3, origem: str = "agenda", log=print) -> dict:
    """Hoje + os `dias_atras` anteriores, numa consulta só.

    A janela existe porque nem toda OS é encerrada no SGP durante o expediente
    (plantão fecha às 19h30, técnico lança no dia seguinte…). Como o upsert é
    por os_id, reprocessar dias já sincronizados é barato e corrige o passado.
    """
    ate = hoje_br()
    de = ate - timedelta(days=max(0, dias_atras))
    return sincronizar(client, de, ate, origem=origem, log=log)


class ProducaoSync(BaseAutomacao):
    slug = "producao-sync"
    nome = "Sincronizar Produção"
    descricao = "Puxa do SGP as OS finalizadas de um período e alimenta o dashboard de Produção."
    cargos = ["admin", "supervisor"]
    parametros = {"de": "", "ate": ""}

    @staticmethod
    def _periodo(params: dict) -> tuple[date, date]:
        """Datas da tela (ISO do input nativo ou BR) → (de, ate).

        A tela já chega com as duas datas preenchidas (o formulário genérico
        preenche campo `date` vazio com hoje), então o caminho normal é "de/até
        do jeito que a pessoa escolheu". Os fallbacks abaixo existem para quem
        chama por fora (script, teste): sem nada, vale a mesma janela da rotina
        das 18h; com só uma ponta, vale aquele dia.
        """
        def ler(valor) -> date | None:
            texto = str(valor or "").strip()
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(texto, fmt).date()
                except ValueError:
                    continue
            return None

        de, ate = ler(params.get("de")), ler(params.get("ate"))
        if not de and not ate:
            hoje = hoje_br()
            return hoje - timedelta(days=3), hoje
        de = de or ate
        ate = ate or de
        return (de, ate) if de <= ate else (ate, de)

    def run(self, params: dict, log) -> Resultado:
        faltando = [k for k in ("SGP_TOKEN", "SGP_APP") if not os.getenv(k)]
        if faltando:
            raise RuntimeError(
                "Configure no worker/.env: " + ", ".join(faltando) +
                " — a produção é lida pela API oficial do SGP (Token/App)."
            )

        from config import get_client  # import tardio: só quem grava precisa

        de, ate = self._periodo(params)
        client = get_client()
        resultado = sincronizar(client, de, ate, origem="manual", log=log)
        linhas = resultado["linhas"]

        P = carregar_script("relatorios/producao_os.py")
        texto = P.resumir(linhas, de, ate)
        texto += f"\n\n{resultado['gravados']} OS gravadas no dashboard de Produção."

        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=CAMPOS_CSV, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)

        arquivos = [
            Arquivo("producao.csv", buf.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"),
            Arquivo("producao.txt", texto.encode("utf-8"), "text/plain; charset=utf-8"),
        ]
        log("Concluído ✓")
        return Resultado(texto=texto, preview=texto[:100_000], arquivos=arquivos)
