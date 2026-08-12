"""Registro das automações. O worker resolve a automação pelo system_slug do job."""
from .base import BaseAutomacao
from .conferencia_checklist import ConferenciaChecklist
from .linhas_canceladas import LinhasCanceladas
from .producao_os import ProducaoSync
from .relatorio_os import RelatorioOS
from .remover_linhas import RemoverLinhas
from .streaming_ativacao import StreamingAtivacao
from .termos_agendados import TermosAgendados
from .verificar_vendas import VerificarVendas

REGISTRY: dict[str, BaseAutomacao] = {
    a.slug: a
    for a in [
        RelatorioOS(),
        TermosAgendados(),
        ConferenciaChecklist(),
        VerificarVendas(),
        StreamingAtivacao(),
        ProducaoSync(),
        LinhasCanceladas(),
        RemoverLinhas(),
    ]
}


def get_automacao(slug: str) -> BaseAutomacao | None:
    return REGISTRY.get(slug)
