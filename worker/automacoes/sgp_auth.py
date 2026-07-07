"""Login web no SGP COM 2FA (segundo fator), dono pelo worker.

O SGP passou a exigir 2FA no /accounts/login/ (redireciona p/ /accounts/confirm-2fa/),
o que quebra o login web simples de Checklist, Linhas Canceladas e Remover Linhas.
Aqui centralizamos o login com 2FA e injetamos nos scripts por monkeypatch (os
scripts em scripts_originais/ ficam intactos — sobrevivem a um novo "drop" do código).

Mecânica descoberta inspecionando as telas reais do SGP:
  login:  POST /accounts/login/        campos: name=username, name=password, csrfmiddlewaretoken
  2fa:    POST /accounts/confirm-2fa/  campos: name=otp, csrfmiddlewaretoken   (botão #entrar)

Credenciais no worker/.env:
  SGP_USER, SGP_PASS  — usuário/senha
  SGP_2FA_SECRET      — o "segredo"/setup key do app autenticador (TOTP). Sem ele o
                        worker não consegue gerar o código e o login web falha limpo.
"""
import os

import pyotp
import requests
from bs4 import BeautifulSoup

BASE = os.getenv("SGP_BASE", "https://giganetwireless.sgp.net.br").rstrip("/")
LOGIN_URL = f"{BASE}/accounts/login/"
CONFIRM_2FA_URL = f"{BASE}/accounts/confirm-2fa/"


def _ssl_verify() -> bool:
    ok = os.getenv("SGP_VERIFY_SSL", "true").strip().lower() not in {"0", "false", "no", "off"}
    if not ok:  # silencia o aviso de HTTPS sem verificação (o SGP usa cert self-signed)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return ok


def _csrf(html: str) -> str:
    el = BeautifulSoup(html, "html.parser").find("input", {"name": "csrfmiddlewaretoken"})
    return (el.get("value") if el else "") or ""


def codigo_2fa() -> str:
    """Gera o código TOTP de 6 dígitos a partir de SGP_2FA_SECRET."""
    seg = (os.getenv("SGP_2FA_SECRET") or "").replace(" ", "")
    if not seg:
        raise RuntimeError(
            "O SGP exige 2FA no login web, mas SGP_2FA_SECRET não está no worker/.env. "
            "Cole o 'segredo'/setup key do app autenticador do SGP (ex.: JBSWY3DPEHPK3PXP)."
        )
    return pyotp.TOTP(seg).now()


def login_requests(session: requests.Session) -> requests.Session:
    """Loga no SGP (usuário + senha + 2FA) numa requests.Session — substitui o
    login_sgp() dos scripts. Deixa a sessão com os cookies autenticados."""
    user, pwd = os.getenv("SGP_USER"), os.getenv("SGP_PASS")
    if not user or not pwd:
        raise RuntimeError("SGP_USER / SGP_PASS não definidos no worker/.env.")
    v = _ssl_verify()
    session.headers.setdefault("User-Agent", "Mozilla/5.0")
    session.headers["Referer"] = LOGIN_URL

    # 1) usuário + senha
    r = session.get(LOGIN_URL, verify=v, timeout=30)
    r.raise_for_status()
    payload = {"username": user, "password": pwd, "csrfmiddlewaretoken": _csrf(r.text)}
    r2 = session.post(LOGIN_URL, data=payload, allow_redirects=True, verify=v, timeout=30)
    r2.raise_for_status()

    # 2) 2FA — só se o SGP pediu o segundo fator (senão já entrou)
    if "confirm-2fa" in r2.url or "confirm-2fa" in r2.text.lower():
        page = session.get(CONFIRM_2FA_URL, verify=v, timeout=30)
        payload2 = {"otp": codigo_2fa(), "csrfmiddlewaretoken": _csrf(page.text)}
        r3 = session.post(CONFIRM_2FA_URL, data=payload2, allow_redirects=True, verify=v, timeout=30)
        r3.raise_for_status()
        if "confirm-2fa" in r3.url or "/accounts/login" in r3.url:
            raise RuntimeError(
                "2FA do SGP recusado (código inválido). Confira SGP_2FA_SECRET e o relógio da máquina."
            )
    return session


def login_playwright(page) -> None:
    """Loga no SGP via Playwright (usuário + senha + 2FA) — usado na fase de
    REMOÇÃO do Remover Linhas, que precisa clicar na tela."""
    user, pwd = os.getenv("SGP_USER"), os.getenv("SGP_PASS")
    if not user or not pwd:
        raise RuntimeError("SGP_USER / SGP_PASS não definidos no worker/.env.")
    page.goto(LOGIN_URL)
    page.fill("input[name='username']", user)
    page.fill("input[name='password']", pwd)
    page.click("#entrar")
    page.wait_for_load_state("load")
    if "confirm-2fa" in page.url:
        page.fill("input[name='otp']", codigo_2fa())
        page.click("#entrar")
        page.wait_for_load_state("load")
