"""Adapter: Verificar Vendas (scripts_originais/vendas/vendas_focus_sgp.py).

Agora 100% via API oficial: o FocusChat (comum/focus_api.py, header access-token)
lista os atendimentos de VENDAS e o SGP (comum/sgp_api.py, Token/App) confere quem
virou cliente. SEM Playwright e SEM 2FA. Leitura (não altera nada)."""
import os
from contextlib import redirect_stdout
from datetime import date, datetime

from .base import Arquivo, BaseAutomacao, Resultado
from .runner import LogWriter, carregar_script


class VerificarVendas(BaseAutomacao):
    slug = "verificar-vendas"
    nome = "Verificar Vendas"
    descricao = "Atendimentos de VENDAS (FocusChat) que ainda não viraram cliente no SGP."
    cargos = ["admin", "supervisor"]
    parametros = {"data": "", "todas": False}

    @staticmethod
    def _resolver_data(params: dict) -> str | None:
        """Converte o que a tela manda no filtro que o script espera (dd/mm/aaaa)
        ou None (todas as datas). Aceita: switch 'todas'; data ISO 'yyyy-mm-dd'
        (input nativo); data BR 'dd/mm/aaaa'; 'hoje'/'todas'; vazio → hoje."""
        todas = params.get("todas")
        if isinstance(todas, str):
            todas = todas.strip().lower() in ("true", "1", "sim", "on")
        if todas:
            return None

        escolha = str(params.get("data") or "").strip()
        if not escolha or escolha.lower() == "hoje":
            return date.today().strftime("%d/%m/%Y")
        if escolha.lower() in ("todas", "todos", "tudo"):
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):  # ISO (input nativo) ou BR
            try:
                return datetime.strptime(escolha, fmt).strftime("%d/%m/%Y")
            except ValueError:
                continue
        return date.today().strftime("%d/%m/%Y")  # formato estranho → hoje

    def run(self, params: dict, log) -> Resultado:
        faltando = [k for k in ("FOCUS_TOKEN", "SGP_TOKEN", "SGP_APP") if not os.getenv(k)]
        if faltando:
            raise RuntimeError(
                "Configure no worker/.env: " + ", ".join(faltando) +
                " — FocusChat e SGP agora usam token de API (sem login web/2FA)."
            )

        V = carregar_script("vendas/vendas_focus_sgp.py")

        filtro = self._resolver_data(params)
        log(f"Coletando vendas no FocusChat ({'todas' if filtro is None else filtro})…")

        try:
            with redirect_stdout(LogWriter(log)):
                vendas = V.coletar_vendas(filtro)
                nao_clientes = V.checar_no_sgp(vendas) if vendas else []
        except SystemExit as e:
            # coletar_vendas() usa SystemExit quando não encontra o setor VENDAS —
            # SystemExit não é Exception, então converto p/ não derrubar o worker.
            raise RuntimeError(str(e) or "Nenhum setor de VENDAS encontrado no FocusChat.")

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
