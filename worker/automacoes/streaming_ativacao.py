"""Adapter: Ativação de Streaming (scripts_originais/relatorios/streaming_ativacao.py).

Relatório diário dos cadastros NOVOS cujo plano inclui streaming (Globoplay,
Max/HBO, Telecine, Watch, Premiere, Disney+) — traz NOME, E-MAIL, TELEFONE, POP
e PLANO p/ a equipe ativar a TV. 100% via API oficial do SGP (Token/App), sem
login web nem 2FA. Rodamos como subprocesso e capturamos a saída."""
import os
from datetime import date, datetime

from .base import Arquivo, BaseAutomacao, Resultado
from .runner import run_script_stream


class StreamingAtivacao(BaseAutomacao):
    slug = "streaming-ativacao"
    nome = "Ativação de Streaming"
    descricao = "Cadastros novos do dia com streaming no plano (o que a equipe precisa p/ ativar a TV)."
    cargos = ["admin", "supervisor"]
    parametros = {"data": ""}

    @staticmethod
    def _resolver_data(params: dict) -> str:
        """A tela manda a data ISO 'yyyy-mm-dd' (input type=date); o script espera
        'dd/mm/aaaa'. Aceita também BR 'dd/mm/aaaa', 'hoje'/vazio (→ hoje)."""
        escolha = str(params.get("data") or "").strip()
        if not escolha or escolha.lower() == "hoje":
            return date.today().strftime("%d/%m/%Y")
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):  # ISO (input nativo) ou BR
            try:
                return datetime.strptime(escolha, fmt).strftime("%d/%m/%Y")
            except ValueError:
                continue
        return date.today().strftime("%d/%m/%Y")  # formato estranho → hoje

    def run(self, params: dict, log) -> Resultado:
        faltando = [k for k in ("SGP_TOKEN", "SGP_APP") if not os.getenv(k)]
        if faltando:
            raise RuntimeError(
                "Configure no worker/.env: " + ", ".join(faltando) +
                " — o relatório de streaming consulta o SGP via token de API."
            )

        dia = self._resolver_data(params)
        log(f"Buscando cadastros novos de {dia} no SGP…")
        texto = run_script_stream("relatorios/streaming_ativacao.py", log,
                                  args=[dia], timeout=240)
        arquivos = [
            Arquivo("streaming-ativacao.txt", texto.encode("utf-8"), "text/plain; charset=utf-8")
        ]
        log("Relatório gerado ✓")
        return Resultado(texto=texto, preview=texto[:100_000], arquivos=arquivos)
