"""
sgp_login.py — Login no SGP com 2FA (TOTP / app autenticador).

Centraliza o login do SGP num só lugar. Depois que o SGP passou a exigir 2FA,
todos os scripts (relatorio_linhas_canceladas, remover_linhas, vendas_focus_sgp,
sgp_cadastro_tv...) devem logar por aqui.

Dois modos de uso:

  A) Playwright (fluxo de tela):
        page = login_playwright(browser)   # já entra com usuário+senha+2FA

  B) requests (consulta/API, ex: autocomplete e relatórios):
        sess = login_requests()            # requests.Session() já autenticada
     -> por baixo, ele faz o login no Playwright (que resolve o 2FA) e
        transfere os cookies pro requests. Assim não precisamos decifrar o
        formulário de 2FA do Django.

Dependências:
    pip install playwright requests python-dotenv pyotp
    python -m playwright install chromium

.env (na mesma pasta):
    SGP_USER=seu_usuario
    SGP_PASS=sua_senha
    SGP_2FA_SECRET=JBSWY3DPEHPK3PXP     # o "segredo" do app autenticador
    # opcional:
    # SGP_2FA_MANUAL=true   -> não usa o segredo, pausa e você digita o código
    # SGP_VERIFY_SSL=false
"""

import os
import pyotp
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

BASE = "https://giganetwireless.sgp.net.br"
LOGIN_URL = f"{BASE}/accounts/login/"

SGP_USER = os.getenv("SGP_USER")
SGP_PASS = os.getenv("SGP_PASS")
SGP_2FA_SECRET = os.getenv("SGP_2FA_SECRET", "").replace(" ", "")
MODO_MANUAL = os.getenv("SGP_2FA_MANUAL", "").lower() in {"1", "true", "yes"}


def gerar_codigo_2fa() -> str:
    """Gera o código de 6 dígitos do momento (TOTP)."""
    if MODO_MANUAL or not SGP_2FA_SECRET:
        return input("Digite o código do 2FA (app autenticador): ").strip()
    return pyotp.TOTP(SGP_2FA_SECRET).now()


def login_playwright(browser, headless_page=None):
    """
    Faz login completo (usuário + senha + 2FA) e devolve uma `page` já logada.
    Passe um `browser` (playwright ...chromium.launch()).
    """
    context = browser.new_context()
    page = context.new_page()
    page.goto(LOGIN_URL)

    # ---- usuário + senha ----
    page.fill("#id_username", SGP_USER)   # >>> VERIFICAR seletor do campo usuário
    page.fill("#id_password", SGP_PASS)   # >>> VERIFICAR seletor do campo senha
    page.click("button[type=submit]")     # >>> VERIFICAR botão "Entrar"

    # ---- 2FA (só aparece agora) ----
    # Espera o campo do código. Ajuste o seletor conforme a tela real do SGP.
    campo_otp = "#id_otp_token"           # >>> VERIFICAR (pode ser name="token")
    try:
        page.wait_for_selector(campo_otp, timeout=5000)
        codigo = gerar_codigo_2fa()
        page.fill(campo_otp, codigo)
        page.click("button[type=submit]")  # >>> VERIFICAR botão "Confirmar"
    except Exception:
        # Se não apareceu o campo, ou o 2FA não foi pedido (dispositivo lembrado),
        # ou o seletor está errado. Descubra o certo com:  playwright codegen <URL>
        pass

    page.wait_for_load_state("networkidle")
    return page


def login_requests() -> requests.Session:
    """
    Devolve uma requests.Session() autenticada, reaproveitando os cookies
    de uma sessão logada via Playwright (que já resolveu o 2FA).
    """
    verify_ssl = os.getenv("SGP_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headed p/ você ver se travar
        page = login_playwright(browser)
        cookies = page.context.cookies()
        browser.close()

    sess = requests.Session()
    sess.verify = verify_ssl
    for c in cookies:
        sess.cookies.set(c["name"], c["value"], domain=c.get("domain"))
    return sess


# Teste rápido: python sgp_login.py
if __name__ == "__main__":
    print("Código 2FA agora:", gerar_codigo_2fa())
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False)
        pg = login_playwright(b)
        print("Logado. URL atual:", pg.url)
        input("ENTER para fechar...")
        b.close()
