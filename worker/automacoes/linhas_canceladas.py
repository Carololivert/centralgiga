"""Adapter: Linhas Canceladas (scripts_originais/relatorio_linhas_canceladas.py).

requests + openpyxl. Varre contratos de telefone cancelados e gera Excel +
lista de números livres. Leitura (não altera nada)."""
import io
from contextlib import redirect_stdout
from datetime import datetime

import requests

from .base import Arquivo, BaseAutomacao, Resultado
from .runner import LogWriter


def intervalo(periodo: str) -> tuple[int, int, int, int]:
    """(ano_ini, mes_ini, ano_fim, mes_fim) a partir do rótulo do período."""
    hoje = datetime.now()
    if periodo == "Este ano":
        return hoje.year, 1, hoje.year, hoje.month
    if periodo.startswith("Últimos 3"):
        ano_i, mes_i = hoje.year, hoje.month - 2
        while mes_i <= 0:
            mes_i += 12
            ano_i -= 1
        return ano_i, mes_i, hoje.year, hoje.month
    return hoje.year, hoje.month, hoje.year, hoje.month  # Este mês


class LinhasCanceladas(BaseAutomacao):
    slug = "linhas-canceladas"
    nome = "Linhas Canceladas"
    descricao = "Números de telefones de contratos cancelados no SGP — gera Excel com os números livres."
    cargos = ["admin", "supervisor"]
    parametros = {"periodo": "Este mês"}

    def run(self, params: dict, log) -> Resultado:
        from scripts_originais import relatorio_linhas_canceladas as R

        periodo = (params.get("periodo") or "Este mês").strip()
        ai, mi, af, mf = intervalo(periodo)
        log(f"Período: {mi:02d}/{ai} a {mf:02d}/{af}")

        rows: list[list[str]] = []
        livres: list[str] = []
        vistos: set[str] = set()

        with redirect_stdout(LogWriter(log)):
            session = requests.Session()
            R.login_sgp(session)
            tokens = R.obter_tokens(session)
            for ano, mes in R.meses_no_intervalo(ai, mi, af, mf):
                print(f"=== {mes:02d}/{ano} ===")
                r = session.get(
                    R.REPORT_URL,
                    params=R.build_params(ano, mes, tokens),
                    verify=R.ssl_verify_enabled(),
                )
                r.raise_for_status()
                contratos = R.parse_contratos(r.text)
                print(f"  {len(contratos)} contrato(s) cancelado(s)")
                for label, url in contratos:
                    numeros = R.extrair_linhas(session, url)
                    if numeros:
                        num, _, nome = label.partition(" - ")
                        rows.append([f"{mes:02d}/{ano}", num.strip(), nome.strip(), "; ".join(numeros)])
                        for n in numeros:
                            if n not in vistos:
                                vistos.add(n)
                                livres.append(n)

        buf = io.BytesIO()
        R.salvar_excel(rows, buf)
        excel_bytes = buf.getvalue()

        linhas = [
            f"LINHAS CANCELADAS — {periodo}",
            "=" * 30,
            f"{len(rows)} contrato(s) com número · {len(livres)} número(s) livre(s)",
            "",
            "Números livres:",
        ]
        linhas += [f"  {n}" for n in livres] if livres else ["  (nenhum)"]
        texto = "\n".join(linhas)

        arquivos = [
            Arquivo(
                "linhas-canceladas.xlsx",
                excel_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        ]
        log("Concluído ✓")
        return Resultado(texto=texto, preview=texto[:100_000], arquivos=arquivos)
