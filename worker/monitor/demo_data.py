#!/usr/bin/env python3
"""
demo_data.py — dados de DEMONSTRAÇÃO do monitor (sem tocar na SmartOLT/SGP).

Ligado por `MONITOR_DEMO=1` no ambiente (ver server.py). Serve para ver o
dashboard funcionando de ponta a ponta sem credenciais — todo payload leva
`"demo": True`, e o front mostra um selo "DEMO". NÃO é dado de produção.

O formato é idêntico ao que `server.py` produz de verdade (mesmas chaves), só
que com valores fixos e caiu_fmt/idade já preenchidos.
"""


def _cli(nome, login, contrato, status_sgp, plano, endereco, tels,
         onu_status, caiu_fmt, olt="3", board=2, port=5):
    """Monta um cliente no mesmo shape de cruza_sgp.resolver_onu()."""
    achou = status_sgp is not None
    return {
        "onu_sn": f"HWTC{abs(hash(login)) % 10**8:08d}",
        "onu_status": onu_status,
        "caiu_em": None,
        "caiu_fmt": caiu_fmt,
        "olt_id": olt, "board": board, "port": port, "onu": abs(hash(login)) % 128,
        "name_olt": login, "address_olt": "",
        "nome": nome, "cpfcnpj": None,
        "endereco": endereco,
        "contrato_id": contrato, "contrato_status": status_sgp,
        "plano": plano, "telefones": tels,
        "via": "login" if achou else None,
        "fonte": "sgp" if achou else "smartolt",
    }


# --- roster de exemplo da PON rompida (OLT 3 · b2/p5 · ARAPONGAS) -----------
_CLIENTES_LOS = [
    _cli("ANA PAULA SOUZA", "ana.souza88", 10432, "Ativo", "Fibra 500 Mega",
         "Rua 12, 45 - Arapongas - Planaltina/GO - 73330-000",
         ["61 99999-1234"], "LOS", "13/07 14:22"),
    _cli("CARLOS EDUARDO LIMA", "carlos.lima21", 10877, "Ativo", "Fibra 700 Mega",
         "Q 04 Cj B, 12 - Arapongas - Planaltina/GO - 73330-010",
         ["61 98888-4567"], "LOS", "13/07 14:22"),
    _cli("MARIA ELUIDES ROCHA ROMEIRO", "maria.rocha172", 9921, "Ativo", "Fibra 300 Mega",
         "Rua das Flores, 200 - Arapongas - Planaltina/GO - 73330-020",
         ["61 97777-8899"], "LOS", "13/07 14:23"),
    _cli("JOÃO BATISTA FERREIRA", "joao.ferreira5", 11002, "Ativo", "Fibra 500 Mega",
         "Av. Central, 1500 - Arapongas - Planaltina/GO - 73330-000",
         ["61 96666-1122"], "LOS", "13/07 14:22"),
    _cli("PEDRO HENRIQUE ALVES", "pedro.alves90", 8123, "Cancelado", None,
         "Rua 7, 88 - Arapongas - Planaltina/GO",
         [], "Offline", "10/07 08:00"),
    _cli("LUCAS MARTINS", "lucas.martins", 7740, "Cancelado", None,
         "Rua 9, 03 - Arapongas - Planaltina/GO",
         [], "LOS", "13/07 14:22"),
    _cli("SANDRA REGINA GOMES", "sandra.gomes33", 10500, "Ativo", "Fibra 400 Mega",
         "Q 02 Cj D, 27 - Arapongas - Planaltina/GO - 73330-030",
         ["61 95555-7788"], "LOS", "13/07 14:22"),
    _cli("(sem nome)", "reserva.b2p5.14", None, None, None, None,
         [], "LOS", "13/07 14:22"),
]
_SEM_HORA = [
    _cli("RAIMUNDO NONATO", "raimundo.n", 6610, "Cancelado", None,
         "Chácara 15 - Zona Rural - Planaltina/GO",
         [], "Power fail", None),
]


def snapshot():
    """Visão geral de demonstração — cenário CRÍTICO (uma PON inteira em LOS)."""
    return {
        "generated_at": "13/07/2026 14:30:12",
        "demo": True,
        "health": "crit",
        "olts": [
            {"id": "1", "nome": "Planaltina", "temp": "31°C", "temp_num": 31,
             "quente": False, "uptime": "45 days"},
            {"id": "2", "nome": "Itapuã", "temp": "30°C", "temp_num": 30,
             "quente": False, "uptime": "45 days"},
            {"id": "3", "nome": "Planaltina-GO", "temp": "37°C", "temp_num": 37,
             "quente": True, "uptime": "12 days"},
        ],
        "totais": {
            "partial_los": {"pons": 6, "subs": 58},
            "los": {"pons": 1, "subs": 96},
            "power": {"pons": 2, "subs": 40},
            "offline": {"pons": 1, "subs": 8},
        },
        "eventos_fibra": [
            {"olt": "Planaltina-GO", "olt_id": "3", "kind": "los",
             "regiao": "ARAPONGAS", "cidade": "Planaltina/GO", "board": 2, "port": 5,
             "total_onus": 96, "los": 96, "power": 0, "offline": 0, "percent": 100,
             "caiu_em": None, "caiu_fmt": "13/07 14:22", "idade_min": 8,
             "idade": "8min", "novo": True},
            {"olt": "Planaltina-GO", "olt_id": "3", "kind": "partial_los",
             "regiao": "JARDIM ROMA", "cidade": "Planaltina/GO", "board": 1, "port": 3,
             "total_onus": 128, "los": 40, "power": 0, "offline": 2, "percent": 33,
             "caiu_em": None, "caiu_fmt": "13/07 14:05", "idade_min": 25,
             "idade": "25min", "novo": True},
            {"olt": "Planaltina", "olt_id": "1", "kind": "partial_los",
             "regiao": "VILA BURITIS", "cidade": "Planaltina/DF", "board": 3, "port": 7,
             "total_onus": 128, "los": 18, "power": 0, "offline": 0, "percent": 14,
             "caiu_em": None, "caiu_fmt": "13/07 09:10", "idade_min": 320,
             "idade": "5h", "novo": False},
            {"olt": "Planaltina", "olt_id": "1", "kind": "partial_los",
             "regiao": "SETOR TRADICIONAL", "cidade": "Planaltina/DF", "board": 0, "port": 1,
             "total_onus": 96, "los": 12, "power": 1, "offline": 0, "percent": 13,
             "caiu_em": None, "caiu_fmt": "12/07 22:40", "idade_min": 960,
             "idade": "16h", "novo": False},
            {"olt": "Itapuã", "olt_id": "2", "kind": "partial_los",
             "regiao": "CENTRO", "cidade": "Itapuã", "board": 2, "port": 4,
             "total_onus": 128, "los": 9, "power": 0, "offline": 1, "percent": 8,
             "caiu_em": None, "caiu_fmt": "11/07 03:12", "idade_min": 2880,
             "idade": "2d", "novo": False},
        ],
        "eventos_energia": [
            {"olt": "Planaltina-GO", "kind": "power", "regiao": "COND. MESTRE D'ARMAS",
             "cidade": "Planaltina/GO", "subs": 28, "caiu_em": None,
             "caiu_fmt": "13/07 13:50", "idade_min": 40, "idade": "40min"},
            {"olt": "Planaltina", "kind": "power", "regiao": "NÚCLEO RURAL",
             "cidade": "Planaltina/DF", "subs": 12, "caiu_em": None,
             "caiu_fmt": "13/07 11:30", "idade_min": 180, "idade": "3h"},
            {"olt": "Itapuã", "kind": "offline", "regiao": "ZONA NÃO MAPEADA",
             "cidade": "", "subs": 8, "caiu_em": None,
             "caiu_fmt": "12/07 18:00", "idade_min": 1200, "idade": "20h"},
        ],
    }


def pon(olt, board, port, janela):
    """Drill-down de demonstração da PON (olt/board/port) cruzada com o SGP."""
    is_rompida = (str(olt), str(board), str(port)) == ("3", "2", "5")

    # Cenário "status ao vivo indisponível" (demonstra o fallback do relatório):
    # VILA BURITIS (OLT 1 · b3/p7) do snapshot demo — o get_onus_statuses viria
    # todo None, então o modal cai para as contagens do relatório de outage.
    if (str(olt), str(board), str(port)) == ("1", "3", "7"):
        return {
            "ok": True, "demo": True,
            "total_pon": 128, "down": 0, "ativos_down": 0,
            "capped": False, "janela": janela,
            "grupos": [], "sem_hora": [], "clientes": [],
            "relatorio": {"kind": "partial_los", "los": 18, "power": 0,
                          "offline": 0, "total": 128, "percent": 14},
            "report_down": 18, "ao_vivo_incompleto": True,
        }

    if is_rompida:
        clientes = list(_CLIENTES_LOS)
        sem_hora = list(_SEM_HORA)
        total_pon, down = 96, 96
    else:
        # PON com perda parcial: só alguns caídos.
        clientes = _CLIENTES_LOS[:4]
        sem_hora = []
        total_pon, down = 128, len(clientes)

    ativos_down = sum(1 for c in clientes
                      if c["contrato_status"] == "Ativo"
                      and c["onu_status"] in ("LOS", "Offline", "Power fail"))

    grupo = {
        "motivo": "LOS", "motivo_label": "LOS (fibra)",
        "n": len(clientes),
        "ativos": ativos_down,
        "caiu_fmt": "13/07 14:22", "span_min": max(0, min(janela, 1)),
        "clientes": clientes,
    }

    return {
        "ok": True, "demo": True,
        "total_pon": total_pon, "down": down, "ativos_down": ativos_down,
        "capped": is_rompida, "janela": janela,
        "grupos": [grupo],
        "sem_hora": sem_hora,
        "clientes": clientes + sem_hora,
        "relatorio": {"kind": "los", "los": down, "power": 0, "offline": 0,
                      "total": total_pon, "percent": 100 if is_rompida else 33},
        "report_down": down, "ao_vivo_incompleto": False,
    }
