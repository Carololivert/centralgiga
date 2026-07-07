#!/usr/bin/env python3
"""
termos_agendados.py - Conferencia de termo das instalacoes agendadas p/ amanha.
Usa a API da URA (/api/ura/ordemservico/list/) - sem 2FA.
"""

import os
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RAIZ, "comum"))
from dotenv import load_dotenv
load_dotenv(os.path.join(_RAIZ, ".env"))

from sgp_api import listar_os

TZ_BR = ZoneInfo("America/Sao_Paulo")


def termo_ok(texto):
    p = (texto or "").lower()
    if re.search(r"\(\s*x\s*\)\s*sim\b", p):
        return True
    if re.search(r"\(\s*x\s*\)\s*entregar\s+termo", p):
        return True
    return False


def texto_da_os(os_item):
    return "\n".join([
        os_item.get("conteudo") or "",
        os_item.get("observacao") or "",
    ])


def eh_instalacao_kit(motivo):
    m = (motivo or "").lower()
    return "instalação de kit" in m or "instalacao de kit" in m


def main():
    hoje = datetime.now(TZ_BR).replace(tzinfo=None)
    amanha = hoje + timedelta(days=1)
    dia = amanha.strftime("%Y-%m-%d")

    os_list = listar_os(
        data_agendamento_inicio=dia,
        data_agendamento_fim=dia,
    )

    instalacoes = [
        o for o in os_list
        if eh_instalacao_kit(o.get("motivo"))
        and (o.get("status") or "").lower() != "encerrada"
    ]

    pendentes = []
    for o in instalacoes:
        if not termo_ok(texto_da_os(o)):
            cliente = (o.get("cliente") or "CLIENTE (sem nome)").strip()
            aberta_por = (o.get("usuario") or "?").strip()
            pendentes.append(f"{cliente}  /  aberta por: {aberta_por}")

    ddmmaa = amanha.strftime("%d/%m/%y")
    print(f"Instalacoes agendadas ({len(instalacoes)}) - conferencia de termo {ddmmaa}:\n")
    if pendentes:
        print("PENDENTE:\n")
        print("\n".join(pendentes))
    else:
        print("OK - todas as instalacoes de amanha estao com o termo.")


if __name__ == "__main__":
    main()