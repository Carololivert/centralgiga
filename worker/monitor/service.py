"""service.py — API HTTP do Monitor SmartOLT, servida numa thread do worker.

Read-only. Dois endpoints (consumidos pela Central via web/server/api/monitor/*,
que exige admin/supervisor):
  GET /api/snapshot                 -> visão geral (temperatura + outage)
  GET /api/pon?olt=&board=&port=    -> clientes de uma PON (cruza SGP)

Roda em daemon thread (make_server), então NÃO bloqueia o loop de jobs do worker.
As credenciais SmartOLT/SGP vêm do worker/.env (carregado por worker/config.py).

Teste standalone (sem worker, dados fictícios):
    cd worker && MONITOR_DEMO=1 python -m monitor.service
"""

import os
import re
import time
import threading
from datetime import datetime
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from . import demo_data

# Modo demo: sem SmartOLT/SGP (dados fictícios). As libs reais só fazem falta
# fora do demo — import tolerante a falha.
DEMO = os.getenv("MONITOR_DEMO", "").strip().lower() in ("1", "true", "yes")
try:
    from . import smartolt_api as sol
    from . import cruza_sgp
    _IMPORT_ERR = None
except Exception as _e:  # pragma: no cover
    sol = cruza_sgp = None
    _IMPORT_ERR = _e

# Token opcional: se definido, /api/* exige o header X-Monitor-Token. Use quando
# a Central (web) rodar em OUTRO host (ex.: Vercel) e alcançar este serviço pela
# rede — protege o endpoint que, sozinho, é aberto.
MONITOR_API_TOKEN = os.getenv("MONITOR_API_TOKEN", "").strip()

# --- cache TTL simples (evita bater na API a cada F5) --------------------
_TTL = 30.0
_cache: dict[str, tuple[float, object]] = {}


def _cached(chave, fn):
    now = time.time()
    hit = _cache.get(chave)
    if hit and (now - hit[0]) < _TTL:
        return hit[1]
    val = fn()
    _cache[chave] = (now, val)
    return val


def _temp_num(env):
    m = re.search(r"-?\d+", str(env or ""))
    return int(m.group()) if m else None


def _idade_min(since):
    if not since:
        return None
    try:
        dt = datetime.strptime(since.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return int((datetime.now() - dt).total_seconds() // 60)


def _fmt_idade(mins):
    if mins is None:
        return "?"
    if mins < 60:
        return f"{mins}min"
    if mins < 1440:
        return f"{mins // 60}h"
    return f"{mins // 1440}d"


def _fmt_dt(since):
    """Data/hora da queda -> 'dd/mm HH:MM' (inclui o ano se não for o atual)."""
    if not since:
        return None
    try:
        dt = datetime.strptime(str(since).strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    fmt = "%d/%m %H:%M" if dt.year == datetime.now().year else "%d/%m/%y %H:%M"
    return dt.strftime(fmt)


def montar_snapshot():
    temps = _cached("temps", sol.temperatura_olts) or []
    olts, eventos_fibra, eventos_energia = [], [], []
    totais = {k: {"pons": 0, "subs": 0} for k in ("partial_los", "los", "power", "offline")}

    for t in temps:
        oid = str(t.get("olt_id"))
        nome = t.get("olt_name", "?")
        tnum = _temp_num(t.get("env_temp"))
        olts.append({
            "id": oid, "nome": nome, "temp": t.get("env_temp"),
            "temp_num": tnum, "quente": tnum is not None and tnum >= 35,
            "uptime": (t.get("uptime") or "").split(",")[0],
        })
        o = _cached(f"outage-{oid}", lambda oid=oid: sol.pons_em_outage(oid))
        secs = {s.get("key"): s for s in (o.get("sections") or [])}
        for k in totais:
            s = secs.get(k, {})
            totais[k]["pons"] += s.get("pon_count", 0) or 0
            totais[k]["subs"] += s.get("subscribers", 0) or 0
        for k in ("partial_los", "los"):
            for g in (secs.get(k, {}).get("groups") or []):
                for p in (g.get("pons") or []):
                    caiu = (p.get("partial_started_at") or p.get("latest_status_change")
                            or g.get("since"))
                    mins = _idade_min(caiu)
                    eventos_fibra.append({
                        "olt": nome, "kind": k,
                        "regiao": p.get("pon_description") or g.get("label") or "?",
                        "cidade": p.get("zone_name") or g.get("sublabel") or "",
                        "board": p.get("board"), "port": p.get("port"), "olt_id": oid,
                        "total_onus": int(p.get("total_onus") or 0),
                        "los": int(p.get("los_count") or 0),
                        "power": int(p.get("power_count") or 0),
                        "offline": int(p.get("offline_count") or 0),
                        "percent": p.get("affected_percent") or 0,
                        "caiu_em": caiu, "caiu_fmt": _fmt_dt(caiu),
                        "idade_min": mins, "idade": _fmt_idade(mins),
                        "novo": mins is not None and mins <= 30,
                    })
        for k in ("power", "offline"):
            for g in (secs.get(k, {}).get("groups") or []):
                caiu = g.get("since")
                mins = _idade_min(caiu)
                eventos_energia.append({
                    "olt": nome, "kind": k,
                    "regiao": g.get("label") or "?", "cidade": g.get("sublabel") or "",
                    "subs": g.get("subscribers", 0),
                    "caiu_em": caiu, "caiu_fmt": _fmt_dt(caiu),
                    "idade_min": mins, "idade": _fmt_idade(mins),
                })

    eventos_fibra.sort(key=lambda e: (0 if e["kind"] == "los" else 1,
                                      e["idade_min"] if e["idade_min"] is not None else 1e9))
    tem_los = totais["los"]["pons"] > 0
    onset_recente = any(e["novo"] for e in eventos_fibra)
    tem_algo = any(v["pons"] for v in totais.values())
    health = "crit" if (tem_los or onset_recente) else ("warn" if tem_algo else "ok")

    return {
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "olts": olts, "totais": totais, "health": health,
        "eventos_fibra": eventos_fibra, "eventos_energia": eventos_energia,
    }


_DOWN = ("LOS", "Offline", "Power fail")
_PRIO = {"LOS": 0, "Offline": 1, "Power fail": 2}
_CAP = 30
JANELA_MIN = 1
_MOTIVO_LABEL = {"LOS": "LOS (fibra)", "Power fail": "energia", "Offline": "offline"}


def _minuto(caiu_em):
    if not caiu_em:
        return None
    try:
        dt = datetime.strptime(str(caiu_em).strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return dt.toordinal() * 1440 + dt.hour * 60 + dt.minute


def _fechar_grupo(motivo, cluster):
    cls = [c for _, c in cluster]
    mins = [mi for mi, _ in cluster]
    pico = Counter(mins).most_common(1)[0][0]
    rep = next(c for mi, c in cluster if mi == pico)
    return {
        "motivo": motivo, "motivo_label": _MOTIVO_LABEL.get(motivo, motivo),
        "n": len(cls),
        "ativos": sum(1 for c in cls if c.get("contrato_status") == "Ativo"),
        "caiu_fmt": rep.get("caiu_fmt"),
        "span_min": max(mins) - min(mins),
        "_ord": max(mins),
        "clientes": cls,
    }


def _agrupar_quedas(clientes, janela):
    sem_hora, por_motivo = [], defaultdict(list)
    for c in clientes:
        if c.get("onu_status") not in _DOWN:
            continue
        mi = _minuto(c.get("caiu_em"))
        if mi is None:
            sem_hora.append(c)
        else:
            por_motivo[c["onu_status"]].append((mi, c))
    grupos = []
    for motivo, itens in por_motivo.items():
        itens.sort(key=lambda x: x[0])
        cluster, prev = [], None
        for mi, c in itens:
            if prev is not None and (mi - prev) > janela:
                grupos.append(_fechar_grupo(motivo, cluster))
                cluster = []
            cluster.append((mi, c))
            prev = mi
        if cluster:
            grupos.append(_fechar_grupo(motivo, cluster))
    grupos.sort(key=lambda g: (-g["n"], -g["_ord"]))
    return grupos, sem_hora


def _pon_report(olt, board, port):
    """Contagem do relatório de outage (get_outage_pons = fonte FIRME) para a PON
    olt/board/port. Serve para NÃO dar all-clear falso quando o status ao vivo
    (get_onus_statuses) vier vazio/None. Reaproveita o cache do snapshot (mesma
    chave 'outage-{olt}'), então normalmente não custa uma chamada extra."""
    try:
        o = _cached(f"outage-{olt}", lambda: sol.pons_em_outage(olt))
    except Exception:
        return None
    secs = {s.get("key"): s for s in (o.get("sections") or [])}
    for k in ("partial_los", "los"):
        for g in (secs.get(k, {}).get("groups") or []):
            for p in (g.get("pons") or []):
                if str(p.get("board")) == str(board) and str(p.get("port")) == str(port):
                    return {
                        "kind": k,
                        "los": int(p.get("los_count") or 0),
                        "power": int(p.get("power_count") or 0),
                        "offline": int(p.get("offline_count") or 0),
                        "total": int(p.get("total_onus") or 0),
                        "percent": p.get("affected_percent") or 0,
                    }
    return None


def criar_app() -> Flask:
    app = Flask(__name__)

    @app.before_request
    def _auth():
        # Sem token configurado: aberto (deploy localhost, mesmo host da Central).
        if not MONITOR_API_TOKEN:
            return None
        if request.path.startswith("/api/"):
            if request.headers.get("X-Monitor-Token", "") != MONITOR_API_TOKEN:
                return jsonify({"ok": False, "erro": "token inválido"}), 401
        return None

    @app.route("/api/snapshot")
    def api_snapshot():
        if DEMO:
            return jsonify({"ok": True, "data": demo_data.snapshot()})
        if sol is None or cruza_sgp is None:
            return jsonify({"ok": False, "erro": f"libs indisponíveis (import falhou): {_IMPORT_ERR}"}), 500
        try:
            return jsonify({"ok": True, "data": montar_snapshot()})
        except Exception as e:
            return jsonify({"ok": False, "erro": str(e)}), 500

    @app.route("/api/pon")
    def api_pon():
        olt = request.args.get("olt", "")
        board = request.args.get("board", "")
        port = request.args.get("port", "")
        try:
            janela = max(0, min(60, int(request.args.get("janela", JANELA_MIN))))
        except ValueError:
            janela = JANELA_MIN
        if DEMO:
            return jsonify(demo_data.pon(olt, board, port, janela))
        if sol is None or cruza_sgp is None:
            return jsonify({"ok": False, "erro": f"libs indisponíveis (import falhou): {_IMPORT_ERR}"}), 500
        try:
            recs = _cached("statuses", sol.status_onus) or []
            roster = [r for r in recs
                      if str(r.get("olt_id")) == olt and str(r.get("board")) == board
                      and str(r.get("port")) == port]
            roster.sort(key=lambda r: _PRIO.get(r.get("status"), 9))
            with ThreadPoolExecutor(max_workers=8) as ex:
                clientes = list(ex.map(cruza_sgp.resolver_onu, roster[:_CAP]))
            for c in clientes:
                c["caiu_fmt"] = _fmt_dt(c.get("caiu_em"))
            down = sum(1 for r in roster if r.get("status") in _DOWN)
            ativos_down = sum(1 for c in clientes
                              if c.get("contrato_status") == "Ativo"
                              and c.get("onu_status") in _DOWN)
            grupos, sem_hora = _agrupar_quedas(clientes, janela)
            # Reconcilia com o relatório de outage (fonte firme). O status ao vivo
            # (get_onus_statuses) é instável: a SmartOLT devolve status=None para
            # ONUs que não poluou há pouco -> down pode vir 0 mesmo com a PON caída.
            rel = _pon_report(olt, board, port)
            report_down = (rel["los"] + rel["power"] + rel["offline"]) if rel else 0
            # Se o relatório aponta quedas mas o ao vivo não reflete, sinaliza que
            # o ao vivo está incompleto (o front não afirma "sem quedas" nesse caso).
            ao_vivo_incompleto = bool(rel and report_down > down)
            return jsonify({"ok": True, "total_pon": len(roster), "down": down,
                            "ativos_down": ativos_down, "capped": len(roster) > _CAP,
                            "janela": janela, "grupos": grupos, "sem_hora": sem_hora,
                            "clientes": clientes,
                            "relatorio": rel, "report_down": report_down,
                            "ao_vivo_incompleto": ao_vivo_incompleto})
        except Exception as e:
            return jsonify({"ok": False, "erro": str(e)}), 500

    @app.route("/")
    def index():
        return jsonify({
            "service": "monitor-smartolt", "ok": True,
            "modo": "demo" if DEMO else "producao",
            "auth": "token" if MONITOR_API_TOKEN else "aberto",
            "endpoints": ["/api/snapshot", "/api/pon?olt=&board=&port=&janela="],
        })

    return app


def iniciar_em_thread(host: str = "127.0.0.1", port: int = 5001):
    """Sobe a API numa daemon thread (não bloqueia o loop do worker).
    Devolve o server (tem .shutdown()). Erros ao subir são propagados p/ quem chamou."""
    app = criar_app()
    srv = make_server(host, port, app, threaded=True)
    t = threading.Thread(target=srv.serve_forever, name="monitor-api", daemon=True)
    t.start()
    return srv


if __name__ == "__main__":
    # Teste standalone: cd worker && MONITOR_DEMO=1 python -m monitor.service
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    _host = os.getenv("MONITOR_HOST", "127.0.0.1")
    _port = int(os.getenv("MONITOR_PORT", "5001"))
    print(f"  Monitor SmartOLT (standalone) em http://{_host}:{_port}  modo={'demo' if DEMO else 'producao'}")
    criar_app().run(host=_host, port=_port, threaded=True)
