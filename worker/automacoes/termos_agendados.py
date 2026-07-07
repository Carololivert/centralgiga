"""Adapter: Termos Agendados (scripts_originais/relatorios/termos_agendados.py).

O script novo usa a API oficial do SGP (URA /ordemservico/list/) — sem login web
e sem 2FA — e já imprime o relatório pronto. Rodamos como subprocesso e usamos a
saída como relatório (os prints de progresso viram logs ao vivo)."""
from .base import Arquivo, BaseAutomacao, Resultado
from .runner import run_script_stream


class TermosAgendados(BaseAutomacao):
    slug = "termos-agendados"
    nome = "Termos Agendados"
    descricao = "Instalações agendadas para amanhã que estão sem o termo preenchido."
    cargos = ["admin", "supervisor"]
    parametros = {}

    def run(self, params: dict, log) -> Resultado:
        log("Consultando o SGP e verificando as instalações de amanhã…")
        texto = run_script_stream("relatorios/termos_agendados.py", log, timeout=180)
        log("Verificação concluída ✓")
        arquivos = [
            Arquivo("termos-agendados.txt", texto.encode("utf-8"), "text/plain; charset=utf-8")
        ]
        return Resultado(texto=texto, preview=texto[:100_000], arquivos=arquivos)
