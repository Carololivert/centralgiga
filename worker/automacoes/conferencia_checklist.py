"""Adapter: Conferência de Checklist (scripts_originais/checklist_equipe.py).

Importa gerar_relatorio_checklist(equipe) e usa o retorno estruturado.
Gera um JSON compacto pra tela (painel por OS) e sobe o JSON completo no Storage.
"""
import json
from contextlib import redirect_stdout

from .base import Arquivo, BaseAutomacao, Resultado
from .runner import LogWriter


class ConferenciaChecklist(BaseAutomacao):
    slug = "conferencia-checklist"
    nome = "Conferência de Checklist"
    descricao = "Avaliação automática (IA) dos checklists das OS de uma equipe."
    cargos = ["admin", "atendente"]
    parametros = {"equipe": "EQUIPE F"}

    def run(self, params: dict, log) -> Resultado:
        from scripts_originais.checklist_equipe import gerar_relatorio_checklist

        equipe = (params.get("equipe") or "EQUIPE F").strip().upper()
        log(f"Analisando checklists da {equipe}…")

        with redirect_stdout(LogWriter(log)):
            dados = gerar_relatorio_checklist(equipe)

        contagem = {"ok": 0, "atencao": 0, "problema": 0, "erro": 0}
        for d in dados:
            s = (d.get("avaliacao") or {}).get("status_geral", "erro")
            contagem[s] = contagem.get(s, 0) + 1

        resumo = (
            f"{len(dados)} OS — {contagem['ok']} ok, {contagem['atencao']} atenção, "
            f"{contagem['problema']} problema, {contagem['erro']} erro"
        )
        log(resumo)

        # estrutura enxuta pra tela (sem os itens/anexos pesados)
        compacto = {
            "equipe": equipe,
            "contagem": contagem,
            "os": [
                {
                    "os_numero": d.get("os_numero"),
                    "os_url": d.get("os_url"),
                    "motivo": d.get("motivo"),
                    "cliente": d.get("cliente"),
                    "responsavel": d.get("responsavel"),
                    "status": (d.get("avaliacao") or {}).get("status_geral", "erro"),
                    "resumo": (d.get("avaliacao") or {}).get("resumo", ""),
                    "problemas": (d.get("avaliacao") or {}).get("problemas", []),
                    "alerta_mac": (d.get("avaliacao") or {}).get("alerta_mac", False),
                    "deslocamento": bool((d.get("deslocamento") or {}).get("teve")),
                    "localizacao": (d.get("localizacao") or {}).get("status"),
                }
                for d in dados
            ],
        }

        completo = json.dumps(dados, ensure_ascii=False, indent=2)
        arquivos = [
            Arquivo("conferencia-checklist.json", completo.encode("utf-8"), "application/json")
        ]
        # painel estruturado vai como JSON no result_preview (a tela detecta pelo sistema)
        return Resultado(preview=json.dumps(compacto, ensure_ascii=False), arquivos=arquivos)
