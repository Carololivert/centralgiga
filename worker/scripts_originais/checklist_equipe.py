import os
import re
import json
import math
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

TZ_BR = ZoneInfo("America/Sao_Paulo")
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://giganetwireless.sgp.net.br"
LOGIN_URL = f"{BASE_URL}/accounts/login"
REPORT_URL = f"{BASE_URL}/admin/atendimento/relatorios/ocorrencia/os/"

EQUIPE_PADRAO = "EQUIPE F"
TODAS_EQUIPES = "TODAS"


def normalizar_texto(txt: str) -> str:
    txt = (txt or "").strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt


def data_brasileira(day: datetime) -> str:
    return day.strftime("%d/%m/%Y")


def ordenar_itens_checklist(itens: list[dict]) -> list[dict]:
    ordem = {
        "a": 1,
        "b": 2,
        "c": 3,
        "d": 4,
        "e": 5,
        "f": 6,
        "g": 7,
        "h": 8,
        "i": 9,
        "j": 10,
        "y": 98,
        "z": 99,
    }

    def chave(item):
        pergunta = normalizar_texto(item.get("pergunta", ""))
        letra = pergunta[:1] if pergunta else "z"
        return ordem.get(letra, 100)

    return sorted(itens, key=chave)


def status_por_problemas(problemas: list[dict]) -> str:
    if not problemas:
        return "ok"

    tipos = {p.get("tipo", "") for p in problemas}
    if "conflito" in tipos or "alerta" in tipos:
        return "problema"
    return "atencao"


def validar_itens_localmente(os_numero: str, motivo: str, itens: list[dict], anexos: list[dict] | None = None) -> dict:
    problemas = []
    alerta_mac = False
    motivo_norm = normalizar_texto(motivo)
    anexos = anexos or []

    if not itens:
        return {
            "status_geral": "atencao",
            "problemas": [],
            "alerta_mac": False,
            "resumo": "Nenhum item de checklist encontrado.",
            "origem": "regra_local",
        }

    perguntas_vistas = {}

    for item in itens:
        pergunta_original = item.get("pergunta", "")
        resposta_original = item.get("resposta", "")
        autor = item.get("autor", "")

        pergunta = normalizar_texto(pergunta_original)
        resposta = normalizar_texto(resposta_original)
        pergunta_fotos = "fotos obrigatórias" in pergunta or "fotos obrigatorias" in pergunta
        tem_imagens_anexadas = any(a.get("eh_imagem") for a in anexos)

        perguntas_vistas.setdefault(pergunta, []).append({
            "resposta": resposta,
            "autor": autor,
            "pergunta_original": pergunta_original,
            "resposta_original": resposta_original,
        })

        if not resposta:
            problemas.append({
                "pergunta": pergunta_original,
                "resposta": resposta_original,
                "autor": autor,
                "tipo": "incompleto",
                "descricao": "Resposta vazia.",
            })
            continue

        if "se sim" in pergunta and resposta == "sim":
            problemas.append({
                "pergunta": pergunta_original,
                "resposta": resposta_original,
                "autor": autor,
                "tipo": "incompleto",
                "descricao": "A pergunta exige detalhamento quando a resposta é 'sim'.",
            })

        pergunta_condicional = "se sim" in pergunta

        pede_valor = any(chave in pergunta for chave in [
            "informar",
            "qual seria",
            "potência",
            "potencia",
            "numero do contrato",
            "número do contrato",
        ])
        if pede_valor and not pergunta_fotos and not (pergunta_condicional and resposta in {"não", "nao"}) and resposta in {"ok", "sim", "não", "nao"}:
            problemas.append({
                "pergunta": pergunta_original,
                "resposta": resposta_original,
                "autor": autor,
                "tipo": "incompleto",
                "descricao": "A pergunta exige um valor concreto, mas a resposta está vaga.",
            })

        if pergunta_fotos:
            if resposta in {"ok"}:
                problemas.append({
                    "pergunta": pergunta_original,
                    "resposta": resposta_original,
                    "autor": autor,
                    "tipo": "suspeito",
                    "descricao": "Resposta genérica para confirmação de fotos obrigatórias.",
                })
            elif resposta == "sim" and not tem_imagens_anexadas:
                problemas.append({
                    "pergunta": pergunta_original,
                    "resposta": resposta_original,
                    "autor": autor,
                    "tipo": "suspeito",
                    "descricao": "A OS indica que as fotos foram incluídas, mas nenhum anexo de imagem foi encontrado.",
                })

    for _, respostas_lista in perguntas_vistas.items():
        respostas_distintas = {r["resposta"] for r in respostas_lista if r["resposta"]}
        if len(respostas_distintas) > 1:
            for r in respostas_lista:
                problemas.append({
                    "pergunta": r["pergunta_original"],
                    "resposta": r["resposta_original"],
                    "autor": r["autor"],
                    "tipo": "conflito",
                    "descricao": "A mesma pergunta teve respostas diferentes.",
                })

    if "troca de equipamento" in motivo_norm:
        tem_item_mac = any(
            any(chave in normalizar_texto(i.get("pergunta", "")) for chave in ["mac", "limpeza", "ativação", "ativacao"])
            for i in itens
        )
        if not tem_item_mac:
            alerta_mac = True
            problemas.append({
                "pergunta": "Verificação de MAC",
                "resposta": "",
                "autor": "",
                "tipo": "alerta",
                "descricao": "Troca de equipamento sem item de limpeza/ativação do MAC.",
            })

    status_geral = status_por_problemas(problemas)

    if status_geral == "ok":
        resumo = "Checklist sem problemas objetivos."
    elif status_geral == "atencao":
        resumo = "Checklist com pontos de atenção."
    else:
        resumo = "Checklist com problemas relevantes."

    return {
        "status_geral": status_geral,
        "problemas": problemas,
        "alerta_mac": alerta_mac,
        "resumo": resumo,
        "origem": "regra_local",
    }


# =========================
# LOGIN
# =========================
def login_sgp(session: requests.Session) -> None:
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": LOGIN_URL,
    })

    username = os.getenv("SGP_USER")
    password = os.getenv("SGP_PASS")
    if not username or not password:
        raise Exception("Variáveis SGP_USER / SGP_PASS não definidas.")

    r = session.get(LOGIN_URL, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    token = soup.find("input", {"name": "csrfmiddlewaretoken"})
    csrf = token["value"] if token else None

    payload = {"username": username, "password": password}
    if csrf:
        payload["csrfmiddlewaretoken"] = csrf

    r2 = session.post(LOGIN_URL, data=payload, allow_redirects=True, timeout=30)
    r2.raise_for_status()


# =========================
# BUSCAR OS DO DIA POR EQUIPE
# =========================
def buscar_os_equipe(session: requests.Session, equipe: str, day: datetime) -> list[dict]:
    d = day.strftime("%d/%m/%Y")
    params = {
        "status": "1",
        "paginate_by": "500",
        "data_agendamento_inicial": f"{d} 00:00:00",
        "data_agendamento_final": f"{d} 23:59:59",
    }

    r = session.get(REPORT_URL, params=params, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.select_one("table#DataTables_Table_0") or soup.select_one("table")
    if not table:
        return []

    headers = [th.get_text(" ", strip=True) for th in table.select("thead th")]
    rows = []

    for tr in table.select("tbody tr"):
        tds = tr.select("td")
        if not tds:
            continue

        row = {}
        for i, td in enumerate(tds):
            key = headers[i] if i < len(headers) else f"col_{i}"
            row[key] = td.get_text(" ", strip=True)
            a = td.find("a", href=True)
            if a:
                row[f"{key}__href"] = a["href"]

        resp = (row.get("Responsável") or "").strip().upper()
        if equipe.upper() != TODAS_EQUIPES and resp != equipe.upper():
            continue

        rows.append(row)

    return rows


# =========================
# EXTRAIR CHECKLIST DA OS
# =========================
def carregar_html_os(session: requests.Session, os_url: str) -> str:
    r = session.get(os_url, timeout=30)
    r.raise_for_status()
    return r.text


def extrair_checklist_do_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    itens = []

    for comentario in soup.select("div#comentarios div.comentario"):
        pergunta_tag = comentario.select_one("div.checklist-and-os div.comentario-checklist")
        resposta_tag = comentario.select_one("div.content.cke_contents_ltr")
        autor_tag = comentario.select_one("div.nome")

        pergunta = pergunta_tag.get_text(" ", strip=True) if pergunta_tag else None
        resposta = resposta_tag.get_text(" ", strip=True) if resposta_tag else None
        autor = autor_tag.get_text(" ", strip=True) if autor_tag else None

        if not pergunta:
            continue

        if autor:
            autor = re.sub(r"\bApagar\b", "", autor, flags=re.IGNORECASE).strip()
            autor = re.sub(r"\s+", " ", autor)

        item = {
            "pergunta": re.sub(r"\s+", " ", (pergunta or "")).strip(),
            "resposta": re.sub(r"\s+", " ", (resposta or "")).strip(),
            "autor": autor,
        }

        itens.append(item)

    unicos = []
    vistos = set()
    for item in itens:
        chave = (item["pergunta"], item["resposta"], item["autor"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(item)

    return ordenar_itens_checklist(unicos)


def extrair_anexos_do_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    anexos = []
    vistos = set()

    for item in soup.select("span.tooltip-anexo-os"):
        nome = (item.get("title") or "").strip()
        link_tag = item.find("a", href=True)
        if not nome or not link_tag:
            continue

        url = urljoin(BASE_URL, link_tag["href"])
        meta = [p.get_text(" ", strip=True) for p in item.select("p.help")]
        data = ""
        autor = ""
        for linha in meta:
            if linha.lower().startswith("data:"):
                data = linha.split(":", 1)[1].strip()
            elif linha.lower().startswith("por:"):
                autor = linha.split(":", 1)[1].strip()

        ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
        eh_imagem = ext in {"jpg", "jpeg", "png", "gif", "webp", "bmp"}
        chave = (nome, url)
        if chave in vistos:
            continue
        vistos.add(chave)

        anexos.append({
            "nome": nome,
            "url": url,
            "data": data,
            "autor": autor,
            "eh_imagem": eh_imagem,
        })

    return anexos


def extrair_contratos_cliente_url(html: str) -> str | None:
    match = re.search(r"'contratosdo':\s*\"([^\"]+)\"", html)
    if not match:
        return None
    return urljoin(BASE_URL, match.group(1))


def extrair_historico_cliente_url(html: str) -> str | None:
    match = re.search(r"'historicodo':\s*\"([^\"]+)\"", html)
    if not match:
        return None
    return urljoin(BASE_URL, match.group(1))


def extrair_servico_internet_url(session: requests.Session, contratos_url: str) -> str | None:
    r = session.get(contratos_url, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    candidatos = []
    for link in soup.select('a[href*="/admin/servicos/internet/"]'):
        href = (link.get("href") or "").strip()
        texto = link.get_text(" ", strip=True)
        if not href:
            continue

        score = 0
        texto_norm = normalizar_texto(texto)
        if "contrato tv" in texto_norm:
            score -= 10
        if "internet" in texto_norm or "fibra" in texto_norm:
            score += 5
        if "ativo" in texto_norm or "online" in texto_norm:
            score += 2

        candidatos.append((score, urljoin(BASE_URL, href)))

    if not candidatos:
        return None

    candidatos.sort(key=lambda item: item[0], reverse=True)
    return candidatos[0][1]


def parse_latlon(valor: str | None) -> tuple[float, float] | None:
    if not valor:
        return None
    partes = [p.strip() for p in str(valor).split(",")]
    if len(partes) != 2:
        return None
    try:
        return float(partes[0]), float(partes[1])
    except ValueError:
        return None


def distancia_metros(coord_a: tuple[float, float], coord_b: tuple[float, float]) -> float:
    lat1, lon1 = coord_a
    lat2, lon2 = coord_b
    raio = 6371000.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return raio * c


def verificar_localizacao(
    session: requests.Session,
    contratos_url: str | None,
    cache_servico: dict[str, dict],
) -> dict:
    resultado = {
        "status": "erro",
        "resumo": "Nao foi possivel validar a localizacao.",
        "cobranca": None,
        "instalacao": None,
        "distancia_metros": None,
        "contratos_url": contratos_url,
        "servico_url": None,
    }

    if not contratos_url:
        resultado["resumo"] = "Pagina de contratos do cliente nao encontrada na OS."
        return resultado

    servico_url = extrair_servico_internet_url(session, contratos_url)
    resultado["servico_url"] = servico_url
    if not servico_url:
        resultado["resumo"] = "Contrato de internet/fibra nao encontrado para este cliente."
        return resultado

    if servico_url not in cache_servico:
        r = session.get(servico_url, timeout=30)
        r.raise_for_status()
        html = r.text
        cache_servico[servico_url] = {
            "cobranca": re.search(r'name="enderecocob-map_ll"[^>]*value="([^"]*)"', html, re.I),
            "instalacao": re.search(r'name="enderecoinst-map_ll"[^>]*value="([^"]*)"', html, re.I),
        }

    info = cache_servico[servico_url]
    cobranca_bruta = info["cobranca"].group(1).strip() if info["cobranca"] else ""
    instalacao_bruta = info["instalacao"].group(1).strip() if info["instalacao"] else ""
    resultado["cobranca"] = cobranca_bruta or None
    resultado["instalacao"] = instalacao_bruta or None

    coord_cobranca = parse_latlon(cobranca_bruta)
    coord_instalacao = parse_latlon(instalacao_bruta)

    if not cobranca_bruta or not instalacao_bruta or not coord_cobranca or not coord_instalacao:
        faltando = []
        if not cobranca_bruta or not coord_cobranca:
            faltando.append("cobranca")
        if not instalacao_bruta or not coord_instalacao:
            faltando.append("instalacao")
        campos = " e ".join(faltando)
        resultado["status"] = "problema"
        resultado["resumo"] = f"Coordenadas ausentes ou invalidas em {campos}."
        return resultado

    dist = distancia_metros(coord_cobranca, coord_instalacao)
    resultado["distancia_metros"] = round(dist, 1)

    if dist <= 30:
        resultado["status"] = "ok"
        resultado["resumo"] = f"Localizacao consistente ({dist:.1f} m de diferenca)."
    elif dist <= 100:
        resultado["status"] = "atencao"
        resultado["resumo"] = f"Coordenadas proximas, mas com diferenca de {dist:.1f} m."
    else:
        resultado["status"] = "problema"
        resultado["resumo"] = f"Coordenadas distantes: {dist:.1f} m entre cobranca e instalacao."

    return resultado


def extrair_linhas_historico(session: requests.Session, historico_url: str) -> list[dict]:
    r = session.get(historico_url, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.select_one("table")
    if not table:
        return []

    headers = [th.get_text(" ", strip=True) for th in table.select("thead th")]
    linhas = []

    for tr in table.select("tbody tr"):
        tds = tr.select("td")
        if not tds:
            continue

        row = {}
        for i, td in enumerate(tds):
            key = headers[i] if i < len(headers) else f"col_{i}"
            row[key] = td.get_text(" ", strip=True)
        linhas.append(row)

    return linhas


def verificar_tecnico_a_caminho(
    session: requests.Session,
    os_numero: str,
    historico_url: str | None,
    day: datetime,
    cache_historico: dict[str, list[dict]],
) -> dict:
    resultado = {
        "teve": False,
        "data": None,
        "usuario": None,
        "mensagem": None,
        "historico_url": historico_url,
    }

    if not historico_url:
        resultado["mensagem"] = "Historico do cliente nao encontrado na OS."
        return resultado

    if historico_url not in cache_historico:
        cache_historico[historico_url] = extrair_linhas_historico(session, historico_url)

    data_hoje = data_brasileira(day)
    padroes_os = [
        re.compile(rf"\bOS[:\s]*{re.escape(os_numero)}\b", re.I),
        re.compile(rf"ordem de servi[cç]o\s*n\.?\s*{re.escape(os_numero)}\b", re.I),
    ]
    padrao_caminho = re.compile(r"indicou que est[áa]\s+a caminho|a caminho do local da ordem", re.I)

    for linha in cache_historico[historico_url]:
        descricao = (linha.get("Histórico") or linha.get("Historico") or "").strip()
        data_evento = (linha.get("Data") or "").strip()
        usuario = (linha.get("Usuário") or linha.get("Usuario") or "").strip()

        if not descricao or not data_evento.startswith(data_hoje):
            continue
        if not padrao_caminho.search(descricao):
            continue
        if not any(p.search(descricao) for p in padroes_os):
            continue

        resultado.update({
            "teve": True,
            "data": data_evento,
            "usuario": usuario or None,
            "mensagem": descricao,
        })
        return resultado

    resultado["mensagem"] = f"Nao encontramos registro de 'a caminho' para a OS {os_numero} em {data_hoje}."
    return resultado


def extrair_os_href(row: dict) -> str | None:
    for key, value in row.items():
        if key.endswith("__href") and value and "/os/" in value:
            return urljoin(BASE_URL, value)
    return None


def extrair_numero_os(row: dict) -> str | None:
    for key, value in row.items():
        if key.endswith("__href") and value:
            m = re.search(r"/os/(\d+)/", value)
            if m:
                return m.group(1)
    return None


# =========================
# MAIN: gerar resultado completo
# =========================
def gerar_relatorio_checklist(equipe: str = EQUIPE_PADRAO) -> list[dict]:
    print(f"[INFO] Iniciando relatório da equipe: {equipe}")

    session = requests.Session()
    login_sgp(session)

    hoje = datetime.now(TZ_BR).replace(tzinfo=None)
    rows = buscar_os_equipe(session, equipe, hoje)

    print(f"[INFO] Total de OS encontradas para {equipe}: {len(rows)}")

    resultado = []
    cache_historico = {}
    cache_servico = {}

    for row in rows:
        os_url = extrair_os_href(row)
        os_numero = extrair_numero_os(row)
        motivo = (row.get("Motivo") or "").strip()

        print(f"[INFO] Processando OS {os_numero} - {motivo}")

        if not os_url or not os_numero:
            continue

        html_os = carregar_html_os(session, os_url)
        itens = extrair_checklist_do_html(html_os)
        anexos = extrair_anexos_do_html(html_os)
        contratos_url = extrair_contratos_cliente_url(html_os)
        historico_url = extrair_historico_cliente_url(html_os)
        deslocamento = verificar_tecnico_a_caminho(session, os_numero, historico_url, hoje, cache_historico)
        localizacao = verificar_localizacao(session, contratos_url, cache_servico)
        print(f"[INFO] OS {os_numero}: {len(itens)} item(ns) de checklist encontrados")
        print(f"[INFO] OS {os_numero}: {len(anexos)} anexo(s) encontrado(s)")
        print(f"[INFO] OS {os_numero}: tecnico a caminho = {deslocamento['teve']}")
        print(f"[INFO] OS {os_numero}: localizacao = {localizacao['status']}")

        avaliacao = validar_itens_localmente(os_numero, motivo, itens, anexos)

        resultado.append({
            "os_numero": os_numero,
            "os_url": os_url,
            "motivo": motivo,
            "cliente": (row.get("Cliente/Contrato") or row.get("Cliente") or "").strip(),
            "responsavel": (row.get("Responsável") or "").strip(),
            "itens": itens,
            "anexos": anexos,
            "avaliacao": avaliacao,
            "deslocamento": deslocamento,
            "localizacao": localizacao,
        })

    try:
        with open("debug_checklist_resultado.json", "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return resultado


if __name__ == "__main__":
    equipe = input("Equipe (ex: EQUIPE F): ").strip() or EQUIPE_PADRAO
    dados = gerar_relatorio_checklist(equipe)

    for os_data in dados:
        av = os_data["avaliacao"]
        status = av.get("status_geral", "?")
        icon = {"ok": "✅", "atencao": "⚠️", "problema": "❌", "erro": "💥"}.get(status, "?")

        print(f"\n{icon} OS {os_data['os_numero']} — {os_data['motivo']}")
        print(f"   {av.get('resumo', '')}")
        print(f"   Origem da análise: {av.get('origem', 'desconhecida')}")

        for p in av.get("problemas", []):
            print(f"   ⚠ {p['pergunta'][:60]}...")
            print(f"     Resposta: {p['resposta']} | {p['descricao']}")

        if av.get("alerta_mac"):
            print("   🔴 ALERTA: Troca de equipamento — verificar limpeza e ativação do MAC!")