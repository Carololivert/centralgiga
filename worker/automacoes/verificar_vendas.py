"""Adapter: Verificar Vendas (scripts_originais/vendas_focus_sgp.py).

FocusChat (Playwright) coleta atendimentos de VENDAS → cruza no SGP →
lista quem NÃO virou cliente. Leitura (não altera nada)."""
from contextlib import redirect_stdout
from datetime import date

from .base import Arquivo, BaseAutomacao, Resultado
from .runner import LogWriter


class VerificarVendas(BaseAutomacao):
    slug = "verificar-vendas"
    nome = "Verificar Vendas"
    descricao = "Atendimentos de VENDAS (FocusChat) que ainda não viraram cliente no SGP."
    cargos = ["admin", "supervisor"]
    parametros = {"data": "hoje"}

    def run(self, params: dict, log) -> Resultado:
        from scripts_originais import vendas_focus_sgp as V

        V.HEADLESS = True  # navegador headless no servidor

        if not V.FOCUS_USER or not V.FOCUS_PASS:
            raise RuntimeError(
                "FOCUS_USER / FOCUS_PASS não configurados no worker/.env (necessários para o FocusChat)."
            )

        escolha = (params.get("data") or "hoje").strip().lower()
        filtro = None if escolha in ("todas", "todos", "tudo") else date.today().strftime("%d/%m/%Y")
        log(f"Coletando vendas no FocusChat ({'todas' if filtro is None else filtro})…")

        with redirect_stdout(LogWriter(log)):
            vendas = V.coletar_vendas(filtro)
            nao_clientes = V.checar_no_sgp(vendas) if vendas else []

        titulo = "VENDAS QUE NÃO CADASTRARAM" + (f" — {filtro}" if filtro else " — todas")
        linhas = [titulo, "=" * len(titulo)]
        if not nao_clientes:
            linhas.append("Nenhum! Todos os atendidos viraram clientes. :)")
        else:
            for i, l in enumerate(nao_clientes, 1):
                nome = (l.get("nome") or "(sem nome)").strip()
                numero = (l.get("numero") or "(sem número)").strip()
                d = (l.get("data") or "").strip()
                obs = "  <- conferir manual" if l.get("status_sgp") == "SEM NUMERO" else ""
                linhas.append(f"{i:>2}. {nome} — {numero} — {d}{obs}")
        linhas += ["", f"Total: {len(nao_clientes)} pessoa(s) que NÃO são clientes"]
        texto = "\n".join(linhas)

        arquivos = [Arquivo("verificar-vendas.txt", texto.encode("utf-8"), "text/plain; charset=utf-8")]
        log("Concluído ✓")
        return Resultado(texto=texto, preview=texto[:100_000], arquivos=arquivos)
