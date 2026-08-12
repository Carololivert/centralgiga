#!/usr/bin/env python3
"""
producao_os.py — Produção do campo: TODA OS finalizada no SGP, normalizada.

É a fonte do dashboard **Produção** da Central (instalações e remoções por POP,
fluxo do dia hora a hora, fechamento mensal). Aqui só se LÊ o SGP e se traduz a
OS crua em uma linha pronta para o banco — quem grava é o worker
(automacoes/producao_os.py).

Como acha as OS finalizadas (o caminho que funciona):
    /api/ura/ordemservico/list/ aceita `data_finalizacao_inicio` / `_fim`, e com
    esse filtro só volta OS "Encerrada" — que é exatamente "o que o técnico
    fechou no dia". (O `/api/os/list/` dá TIMEOUT; o filtro por
    `data_agendamento` traz também o que ficou em aberto, que não é produção.)

Limites da API (medidos): `limit` vai até 1000 (1500 devolve 400); a resposta
traz `paginacao.total`, então paginamos por `offset` até fechar o total.

Uso:
    python relatorios/producao_os.py                      # hoje
    python relatorios/producao_os.py 10/08/2026           # um dia
    python relatorios/producao_os.py 01/07/2026 31/07/2026  # período (mês)

Credenciais (no .env da raiz): SGP_BASE, SGP_TOKEN, SGP_APP.
"""

import csv
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RAIZ, "comum"))
load_dotenv(os.path.join(_RAIZ, ".env"))

# Console do Windows (cp1252) quebra com acento em nome de cliente/POP.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import sgp_api  # noqa: E402

TZ_BR = ZoneInfo("America/Sao_Paulo")
ENDPOINT = "/api/ura/ordemservico/list/"
LIMITE_PAGINA = 500          # a API aceita até 1000; 500 mantém a resposta leve
SAIDA = "producao_os.csv"


# ============================================================
# CLASSIFICAÇÃO DO MOTIVO
# ============================================================
# O SGP não tem campo de "tipo de serviço" — a informação está no texto do
# motivo. As regras abaixo são avaliadas EM ORDEM (a primeira que casar vence),
# então o específico vem antes do genérico.
#
# categoria: instalacao | remocao | mudanca | corretiva | rompimento |
#            servico | outros
#
# Para incluir um motivo novo, basta somar uma linha aqui — nada mais no
# sistema precisa mudar (o painel monta os gráficos a partir da categoria).
REGRAS = [
    # (categoria, padrão no motivo — já sem acento e em minúsculas)
    ("instalacao", r"^instalacao de kit"),
    ("remocao",    r"^remocao de kit"),
    ("mudanca",    r"^mudanca endereco"),
    ("servico",    r"cabo de rede|entrega de carne|recuperacao de equipamento"
                   r"|manutencao preventiva|ajuste de rede"),
    # ⚠️ corretiva ANTES de rompimento, de propósito: o motivo
    # "Corretiva - offline (não considerar fibra quebrada)" cita "fibra
    # quebrada" no aviso entre parênteses. Sem esta ordem (e sem o ^ no padrão
    # de rompimento) essas ~54 OS/mês entravam como rompimento e inflavam o
    # gráfico de fibra.
    ("corretiva",  r"^corretiva|potencia alta|troca de equipamento"
                   r"|troca de posicao|teste velocidade|ocorrencia/os"
                   r"|offline|lentidao"),
    ("rompimento", r"^fibra quebrada|rompimento"),
]

# Onde o serviço aconteceu — só faz sentido para instalação/remoção/mudança.
SUBCATEGORIAS = [
    ("condominio", r"condominio"),       # cobre "retirada portaria condomínio"
    ("predio",     r"apartamento/predio|predio geral"),
    ("diverso",    r"local diverso"),
    ("contrato",   r"local do contrato"),
    ("casa",       r"casa"),
]


def _norm(txt: str) -> str:
    """minúsculas, sem acento, espaços colapsados — para casar as regras."""
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", txt).strip().lower()


def classificar(motivo: str) -> tuple[str, str | None]:
    """Motivo cru do SGP -> (categoria, subcategoria)."""
    m = _norm(motivo)
    if not m:
        return "outros", None

    categoria = "outros"
    for cat, padrao in REGRAS:
        if re.search(padrao, m):
            categoria = cat
            break

    subcategoria = None
    if categoria in ("instalacao", "remocao", "mudanca"):
        for sub, padrao in SUBCATEGORIAS:
            if re.search(padrao, m):
                subcategoria = sub
                break

    return categoria, subcategoria


def partes_do_pop(pop: str) -> tuple[int | None, str | None]:
    """'Fibra 5 - Itapõa' -> (5, 'Itapõa').  'POP EVENTOS/TESTES' -> (None, ...)."""
    texto = (pop or "").strip()
    if not texto:
        return None, None
    m = re.match(r"^\s*fibra\s*(\d+)\s*-\s*(.+)$", texto, re.IGNORECASE)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, texto


# ============================================================
# LEITURA NO SGP
# ============================================================
MAX_PAGINAS = 200  # trava de segurança: ~100 mil OS, muito acima de qualquer mês


def listar_finalizadas(de_iso: str, ate_iso: str, log=print) -> list[dict]:
    """OS finalizadas entre as duas datas (ISO yyyy-mm-dd), paginando por offset."""
    todas: list[dict] = []
    offset = 0
    for _ in range(MAX_PAGINAS):
        resp = sgp_api.chamar(
            ENDPOINT,
            data_finalizacao_inicio=de_iso,
            data_finalizacao_fim=ate_iso,
            limit=LIMITE_PAGINA,
            offset=offset,
        )
        if not isinstance(resp, dict):
            break
        lote = resp.get("ordens_servicos") or []
        total = (resp.get("paginacao") or {}).get("total")
        todas += lote
        if not lote:
            break
        if isinstance(total, int):
            log(f"  … {len(todas)}/{total} OS")
            if len(todas) >= total:
                break
        elif len(lote) < LIMITE_PAGINA:
            break
        offset += LIMITE_PAGINA
    else:
        log(f"⚠️ parei em {MAX_PAGINAS} páginas ({len(todas)} OS) — período grande demais.")
    return todas


def _data(valor) -> date | None:
    try:
        return datetime.strptime(str(valor).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _hora(valor) -> str | None:
    txt = str(valor or "").strip()
    return txt if re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", txt) else None


def normalizar(item: dict) -> dict | None:
    """OS crua do SGP -> linha da tabela os_producao. None se não der pra usar."""
    os_id = item.get("id")
    finalizacao = _data(item.get("data_finalizacao"))
    if not os_id or not finalizacao:
        return None  # sem id ou sem dia de finalização não é produção

    motivo = (item.get("motivo") or "").strip()
    categoria, subcategoria = classificar(motivo)
    pop = (item.get("pop") or "").strip()
    pop_num, pop_regiao = partes_do_pop(pop)
    hora = _hora(item.get("hora_finalizacao"))
    cadastro = _data(item.get("data_cadastro"))
    agendamento = _data(item.get("data_agendamento"))

    # timestamp com fuso: sem isso o Postgres assumiria UTC e a OS das 17h
    # apareceria às 20h no gráfico do dia.
    finalizado_em = None
    if hora:
        h, m, *resto = hora.split(":")
        finalizado_em = datetime(
            finalizacao.year, finalizacao.month, finalizacao.day,
            int(h), int(m), int(resto[0]) if resto else 0, tzinfo=TZ_BR,
        ).isoformat()

    tecnicos = [t for t in (item.get("tecnicos_auxiliares") or []) if t]

    return {
        "os_id": int(os_id),
        "ocorrencia": (item.get("ocorrencia") or "").strip() or None,
        "cliente": (item.get("cliente") or "").strip() or None,
        "contrato": item.get("contrato") if isinstance(item.get("contrato"), int) else None,
        "contrato_status": (item.get("contrato_status") or "").strip() or None,
        "tipo": (item.get("tipo") or "").strip() or None,
        "status": (item.get("status") or "").strip() or None,
        "motivo": motivo,
        "categoria": categoria,
        "subcategoria": subcategoria,
        "pop": pop or None,
        "pop_num": pop_num,
        "pop_regiao": pop_regiao,
        "equipe": (item.get("responsavel") or "").strip() or None,
        "usuario_abertura": (item.get("usuario") or "").strip() or None,
        "usuario_finalizacao": (item.get("usuario_finalizacao") or "").strip() or None,
        "tecnicos": tecnicos,
        "data_cadastro": cadastro.isoformat() if cadastro else None,
        "data_agendamento": agendamento.isoformat() if agendamento else None,
        "data_finalizacao": finalizacao.isoformat(),
        "hora_finalizacao": hora,
        "finalizado_em": finalizado_em,
        "espera_dias": (finalizacao - cadastro).days if cadastro else None,
    }


def coletar(de: date, ate: date, log=print) -> list[dict]:
    """Linhas prontas para o banco, do período pedido (inclusive nas duas pontas)."""
    log(f"Lendo OS finalizadas de {de:%d/%m/%Y} a {ate:%d/%m/%Y} no SGP…")
    cruas = listar_finalizadas(de.isoformat(), ate.isoformat(), log=log)
    linhas = [x for x in (normalizar(o) for o in cruas) if x]
    log(f"{len(linhas)} OS finalizadas ({len(cruas) - len(linhas)} descartadas por falta de id/data).")
    return linhas


# ============================================================
# RESUMO EM TEXTO (o que aparece na tela da automação)
# ============================================================
ROTULOS = {
    "instalacao": "Instalações",
    "remocao": "Remoções",
    "mudanca": "Mudanças de endereço",
    "corretiva": "Corretivas",
    "rompimento": "Rompimentos (fibra)",
    "servico": "Serviços/entregas",
    "outros": "Outros",
}
ORDEM = ["instalacao", "remocao", "mudanca", "corretiva", "rompimento", "servico", "outros"]


def resumir(linhas: list[dict], de: date, ate: date) -> str:
    """Fechamento em texto: totais por categoria, por POP e por equipe."""
    titulo = (f"PRODUÇÃO — {de:%d/%m/%Y}" if de == ate
              else f"PRODUÇÃO — {de:%d/%m/%Y} a {ate:%d/%m/%Y}")
    out = ["=" * 62, f"  {titulo}", "=" * 62]

    if not linhas:
        out += ["  Nenhuma OS finalizada no período.", "=" * 62]
        return "\n".join(out)

    por_cat = Counter(l["categoria"] for l in linhas)
    out.append(f"  Total de OS finalizadas: {len(linhas)}")
    for cat in ORDEM:
        if por_cat.get(cat):
            out.append(f"    {por_cat[cat]:4d}  {ROTULOS[cat]}")

    instal_remoc = [l for l in linhas if l["categoria"] in ("instalacao", "remocao")]
    if instal_remoc:
        out += ["", "  Instalações e remoções por POP:"]
        por_pop = Counter(l["pop"] or "(sem POP)" for l in instal_remoc)
        for pop, n in por_pop.most_common():
            i = sum(1 for l in instal_remoc if (l["pop"] or "(sem POP)") == pop
                    and l["categoria"] == "instalacao")
            out.append(f"    {n:4d}  {pop}  ({i} instalação(ões), {n - i} remoção(ões))")

    out += ["", "  Por equipe:"]
    por_eq = Counter(l["equipe"] or "(sem equipe)" for l in linhas)
    for eq, n in por_eq.most_common():
        i = sum(1 for l in linhas if (l["equipe"] or "(sem equipe)") == eq
                and l["categoria"] == "instalacao")
        r = sum(1 for l in linhas if (l["equipe"] or "(sem equipe)") == eq
                and l["categoria"] == "remocao")
        out.append(f"    {n:4d}  {eq}  ({i} instalação(ões), {r} remoção(ões))")

    # motivos que não se encaixaram: é o sinal de que falta uma regra em REGRAS
    nao_classificados = Counter(l["motivo"] for l in linhas if l["categoria"] == "outros")
    if nao_classificados:
        out += ["", "  ⚠️ Motivos sem categoria (entram como 'Outros'):"]
        for motivo, n in nao_classificados.most_common(15):
            out.append(f"    {n:4d}  {motivo}")

    out.append("=" * 62)
    return "\n".join(out)


# ============================================================
# MAIN (uso avulso, fora da Central)
# ============================================================
def _arg_data(valor: str) -> date:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor, fmt).date()
        except ValueError:
            continue
    raise SystemExit(f"Data inválida: {valor} (use dd/mm/aaaa)")


def main():
    hoje = datetime.now(TZ_BR).date()
    args = sys.argv[1:]
    de = _arg_data(args[0]) if args else hoje
    ate = _arg_data(args[1]) if len(args) > 1 else de
    if de > ate:
        de, ate = ate, de

    linhas = coletar(de, ate)

    campos = ["os_id", "data_finalizacao", "hora_finalizacao", "categoria", "subcategoria",
              "motivo", "pop", "pop_num", "pop_regiao", "equipe", "cliente", "contrato",
              "contrato_status", "usuario_finalizacao", "data_cadastro", "espera_dias"]
    with open(SAIDA, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)

    print()
    print(resumir(linhas, de, ate))
    print(f"  (detalhe salvo em {SAIDA})")


if __name__ == "__main__":
    main()
