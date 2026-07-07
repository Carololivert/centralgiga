"""Adapter: Relatório de OS do dia por equipe.

Script novo (scripts_originais/relatorios/main.py) usa a API oficial do SGP
(URA), sem login web nem 2FA. Rodamos como subprocesso e capturamos a saída."""
from .base import Arquivo, BaseAutomacao, Resultado
from .runner import run_script_stream


class RelatorioOS(BaseAutomacao):
    slug = "relatorio-os"
    nome = "Relatório de OS"
    descricao = "Resumo por equipe (A–I) das OS finalizadas do dia."
    cargos = ["admin", "supervisor"]
    parametros = {}

    def run(self, params: dict, log) -> Resultado:
        log("Conectando ao SGP e gerando o relatório do dia…")
        texto = run_script_stream("relatorios/main.py", log, timeout=180)
        arquivos = [
            Arquivo("relatorio-os.txt", texto.encode("utf-8"), "text/plain; charset=utf-8")
        ]
        log("Relatório gerado ✓")
        # preview = relatório completo (exibido na tela); cap só por segurança
        return Resultado(texto=texto, preview=texto[:100_000], arquivos=arquivos)
