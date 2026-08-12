"""Adapter: Verificar Vendas (scripts_originais/vendas/vendas_focus_sgp.py).

Agora 100% via API oficial: o FocusChat (comum/focus_api.py, header access-token)
lista os atendimentos de VENDAS e o SGP (comum/sgp_api.py, Token/App) confere quem
virou cliente. SEM Playwright e SEM 2FA. Leitura (não altera nada).

O texto do resultado sai no formato de COLAR NO WHATSAPP (uma pessoa por linha:
nome, número, região, etiqueta de sem cobertura) — igual ao que o script imprime.
O detalhe completo (status no SGP e a frase que provou a recusa) vai no CSV anexo."""
import csv
import io
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
        # FocusChat aceita 1 canal (FOCUS_TOKEN) OU vários (FOCUS_TOKENS, separados
        # por vírgula). Basta um dos dois estar preenchido — o token é POR CANAL.
        faltando = []
        if not (os.getenv("FOCUS_TOKEN") or os.getenv("FOCUS_TOKENS")):
            faltando.append("FOCUS_TOKEN (ou FOCUS_TOKENS p/ vários canais)")
        faltando += [k for k in ("SGP_TOKEN", "SGP_APP") if not os.getenv(k)]
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
                # 2b) lê as conversas dos não-clientes e, no mesmo passo, etiqueta a
                # recusa por cobertura (sem_cobertura/trecho_cobertura) e a região
                # citada na conversa (local).
                if nao_clientes:
                    V.analisar_cobertura(nao_clientes)
        except SystemExit as e:
            # coletar_vendas() usa SystemExit quando não encontra o setor VENDAS —
            # SystemExit não é Exception, então converto p/ não derrubar o worker.
            raise RuntimeError(str(e) or "Nenhum setor de VENDAS encontrado no FocusChat.")

        # checar_no_sgp() joga na mesma lista quem foi CONFERIDO e deu não-cliente
        # ("NAO CADASTRADO") e quem NÃO deu pra conferir ("SEM NUMERO" ou "ERRO: …",
        # ex. token vencido/SGP fora do ar). Sem marcar, um SGP fora do ar faria o
        # dia inteiro sair como "não finalizou" — por isso a marca de conferir.
        def _conferir(l) -> str:
            st = (l.get("status_sgp") or "").strip()
            if st == "SEM NUMERO":
                return " ⚠️ conferir (sem número)"
            if st.startswith("ERRO"):
                return " ⚠️ conferir (falha ao consultar o SGP)"
            return ""

        # Uma pessoa por linha, pronto p/ colar no WhatsApp: nome, número, região.
        linhas = [f"📋 VENDAS NÃO FINALIZADAS ({filtro or 'todas as datas'})", ""]
        if not nao_clientes:
            linhas.append("Nenhum! Todos os atendidos viraram clientes. :)")
        else:
            for l in nao_clientes:
                nome = (l.get("nome") or "").strip() or "sem nome"
                numero = (l.get("numero") or "").strip()
                numero = f"+55 {numero}" if numero else "(sem número)"
                local = (l.get("local") or "").strip() or "não informou o local"
                tag = " [SEM COBERTURA]" if l.get("sem_cobertura") == "SIM" else ""
                linhas.append(f"{nome} {numero} {local}{tag}{_conferir(l)}")
        n_cob = sum(1 for l in nao_clientes if l.get("sem_cobertura") == "SIM")
        n_conf = sum(1 for l in nao_clientes if _conferir(l))
        rodape = f"({len(nao_clientes)} não finalizadas · {n_cob} sem cobertura"
        rodape += f" · {n_conf} a conferir)" if n_conf else ")"
        linhas += ["", rodape]
        if n_conf:
            linhas.append("⚠️ As linhas marcadas NÃO foram conferidas no SGP — "
                          "podem já ser clientes.")
        texto = "\n".join(linhas)

        # CSV com o detalhe que não cabe no texto (status no SGP e a frase que
        # provou a recusa). utf-8-sig p/ o Excel abrir com acento certo.
        buf = io.StringIO()
        campos = ["nome", "numero", "data", "local", "status_sgp",
                  "sem_cobertura", "trecho_cobertura"]
        w = csv.DictWriter(buf, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for l in nao_clientes:
            w.writerow({c: l.get(c, "") for c in campos})

        # ⚠️ A ORDEM IMPORTA: worker.subir_arquivos() sobe todos, mas só o PRIMEIRO
        # vira jobs.result_path — que é o único que o botão "Baixar" da tela assina.
        # Por isso o CSV vem primeiro: o .txt é idêntico ao texto já exibido na tela
        # (que tem botão de copiar), enquanto o CSV é o único lugar com data,
        # status_sgp e a frase que provou a recusa.
        arquivos = [
            Arquivo("verificar-vendas.csv", buf.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"),
            Arquivo("verificar-vendas.txt", texto.encode("utf-8"), "text/plain; charset=utf-8"),
        ]
        log("Concluído ✓")
        return Resultado(texto=texto, preview=texto[:100_000], arquivos=arquivos)
