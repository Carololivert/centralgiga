# Worker da Central Giganet (Python + Playwright/Chromium)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=America/Sao_Paulo

WORKDIR /app

# Dependências Python + Chromium (com libs de sistema) do Playwright
COPY requirements.txt .
RUN pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium

# Código do worker (a .env NÃO entra na imagem — variáveis vêm do painel)
COPY . .

# Loop do worker (reivindica jobs e executa). Sem porta exposta (só saída).
CMD ["python", "worker.py"]
