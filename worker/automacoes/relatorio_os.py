"""Adapter: Relatório de OS do dia por equipe (scripts_originais/main.py)."""
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
        texto = run_script_stream("main.py", log, timeout=180)
        arquivos = [
            Arquivo("relatorio-os.txt", texto.encode("utf-8"), "text/plain; charset=utf-8")
        ]
        log("Relatório gerado ✓")
        # preview = relatório completo (exibido na tela); cap só por segurança
        return Resultado(texto=texto, preview=texto[:100_000], arquivos=arquivos)
