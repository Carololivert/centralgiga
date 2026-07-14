# Worker da Central Giganet (Python + Playwright/Chromium)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=America/Sao_Paulo

# Monitor SmartOLT: no container a API precisa escutar em 0.0.0.0 (não 127.0.0.1)
# para o proxy do easypanel/Docker alcançar. Porta interna 5001.
ENV MONITOR_HOST=0.0.0.0 \
    MONITOR_PORT=5001

WORKDIR /app

# Dependências Python + Chromium (com libs de sistema) do Playwright
COPY requirements.txt .
RUN pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium

# Código do worker (a .env NÃO entra na imagem — variáveis vêm do painel)
COPY . .

# API do Monitor de Rede (consumida pela Central via proxy). Exponha esta porta
# no easypanel (Domains → porta 5001) para a web na Vercel alcançar.
EXPOSE 5001

# Um processo só: o loop de jobs + a API do monitor (thread). Ver worker.py.
CMD ["python", "worker.py"]
