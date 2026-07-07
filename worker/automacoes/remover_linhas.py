"""Adapter: Remover Linhas (scripts_originais/telefonia/remover_linhas.py).

AÇÃO DESTRUTIVA — remove no SGP as linhas de telefonia de contratos cancelados.
Por padrão roda em SIMULAÇÃO (dry_run=True): só mostra o que removeria.
Playwright + login web (SGP_USER/SGP_PASS). Só admin. Auditável."""
from contextlib import redirect_stdout

from .base import BaseAutomacao, Resultado
from .linhas_canceladas import intervalo
from .runner import LogWriter, carregar_script


class RemoverLinhas(BaseAutomacao):
    slug = "remover-linhas"
    nome = "Remover Linhas"
    descricao = "Remove no SGP as linhas de contratos cancelados. Rode a simulação antes de remover de verdade."
    cargos = ["admin"]
    parametros = {"dry_run": True, "periodo": "Este mês"}
    auditavel = True

    def run(self, params: dict, log) -> Resultado:
        from .sgp_auth import login_playwright, login_requests

        R = carregar_script("telefonia/remover_linhas.py")
        R.login_sgp = login_requests        # fase descobrir() (requests) — com 2FA
        R.login_playwright = login_playwright  # fase de remoção (Playwright) — com 2FA

        v = params.get("dry_run", True)
        dry = True if v is None else bool(v)
        periodo = (params.get("periodo") or "Este mês").strip()
        ai, mi, af, mf = intervalo(periodo)

        R.DRY_RUN = dry
        R.HEADLESS = True
        R.ANO_INICIO, R.MES_INICIO = ai, mi
        R.ANO_FIM, R.MES_FIM = af, mf

        modo = "SIMULAÇÃO (nada será removido)" if dry else "REMOÇÃO REAL"
        log(f"Modo: {modo} · período {mi:02d}/{ai}–{mf:02d}/{af}")

        with redirect_stdout(LogWriter(log)):
            servicos = R.descobrir()
            print(f"{len(servicos)} serviço(s) com número a liberar.")
            reg, rem = R.processar(servicos)

        linhas = [
            f"REMOVER LINHAS — {modo}",
            "=" * 30,
            f"Serviços encontrados: {len(servicos)}",
        ]
        if dry:
            linhas.append(f"Linhas que SERIAM removidas: {reg}")
            linhas.append("Se estiver correto, rode de novo desmarcando 'Apenas simular'.")
        else:
            linhas.append(f"Linhas REMOVIDAS: {rem}")
        texto = "\n".join(linhas)
        log("Concluído ✓")
        return Resultado(texto=texto, preview=texto)
