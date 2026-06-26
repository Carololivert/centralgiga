"""Contrato base das automações."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# log(linha: str, nivel: str = "info") -> grava em job_logs em tempo real
LogFn = Callable[..., None]


@dataclass
class Arquivo:
    nome: str
    conteudo: bytes
    content_type: str = "application/octet-stream"


@dataclass
class Resultado:
    texto: str | None = None          # texto principal (relatório)
    # result_preview exibido inline: texto puro (relatórios) OU JSON (painel do checklist)
    preview: str | None = None
    arquivos: list[Arquivo] = field(default_factory=list)  # vão pro Storage


class BaseAutomacao:
    """Cada sistema implementa run(). Metadados são informativos
    (a permissão real vem da tabela `systems` no Supabase)."""

    slug: str = ""
    nome: str = ""
    descricao: str = ""
    cargos: list[str] = []
    parametros: dict = {}

    def run(self, params: dict, log: LogFn) -> Resultado:
        raise NotImplementedError
