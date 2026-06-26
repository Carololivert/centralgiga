"""Adapter: Termos Agendados (scripts_originais/termos_agendados.py).

Chama a função existente in-process (com a mesma cola do main() do script)
e usa o texto RETORNADO como relatório — os prints de debug viram logs."""
from contextlib import redirect_stdout
from datetime import timedelta

import requests

from .base import Arquivo, BaseAutomacao, Resultado
from .runner import LogWriter


class TermosAgendados(BaseAutomacao):
    slug = "termos-agendados"
    nome = "Termos Agendados"
    descricao = "Instalações agendadas para amanhã que estão sem o termo preenchido."
    cargos = ["admin", "supervisor"]
    parametros = {}

    def run(self, params: dict, log) -> Resultado:
        from scripts_originais import termos_agendados as T

        log("Conectando ao SGP e verificando instalações de amanhã…")
        session = requests.Session()
        with redirect_stdout(LogWriter(log)):
            T.login_sgp(session)
            amanha = T.datetime.now(T.TZ_BR).replace(tzinfo=None) + timedelta(days=1)
            texto = T.gerar_relatorio_instalacoes_agendadas(session, amanha)

        log("Verificação concluída ✓")
        arquivos = [
            Arquivo("termos-agendados.txt", texto.encode("utf-8"), "text/plain; charset=utf-8")
        ]
        return Resultado(texto=texto, preview=texto[:100_000], arquivos=arquivos)
