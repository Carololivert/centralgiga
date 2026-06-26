# Worker — Central Giganet

Processo Python que observa a fila de `jobs` no Supabase, executa a automação
correspondente (reaproveitando os scripts de `scripts_originais/`) e grava
logs ao vivo + resultado de volta.

> Os scripts atuais usam `requests` + `BeautifulSoup` (**não** Playwright),
> então o worker é leve: não precisa de Chromium. Roda no seu PC ou num VPS.
> A `service_role` key fica **só aqui**.

## Estrutura

```
worker/
├─ worker.py                 # loop: claim_next_job → executa → grava resultado
├─ config.py                 # .env + client Supabase (service_role)
├─ automacoes/
│  ├─ base.py                # BaseAutomacao / Resultado / Arquivo
│  ├─ runner.py              # roda scripts e transmite stdout p/ log ao vivo
│  ├─ registry.py            # slug → automação
│  └─ relatorio_os.py        # adapter do main.py (Etapa 3)
├─ scripts_originais/        # cópia fiel dos scripts do Aut-SGP
├─ requirements.txt
├─ .env.example
└─ deploy/worker.service
```

## Rodar localmente (Windows/PowerShell)

```powershell
cd worker
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # preencha SUPABASE_SERVICE_ROLE_KEY e as credenciais SGP
python worker.py
```

No Linux/Mac troque por `source venv/bin/activate` e `cp`.

O worker fica em loop. Quando alguém clica **Executar** na central, aparece:

```
[worker] job <uuid> · relatorio-os
  [xxxxxxxx] Conectando ao SGP e gerando o relatório do dia…
  [xxxxxxxx] ############################################################
  ...
  [xxxxxxxx] Relatório gerado ✓
  [xxxxxxxx] Resultado salvo no Storage: relatorio-os.txt
  [xxxxxxxx] Concluído ✓
```

## Deploy no VPS (systemd)

```bash
sudo mkdir -p /opt/giganet-central
sudo cp -r worker /opt/giganet-central/
cd /opt/giganet-central/worker
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env        # preencher

sudo cp deploy/worker.service /etc/systemd/system/giganet-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now giganet-worker
journalctl -u giganet-worker -f
```

## Como testar ponta a ponta

1. Rode as migrations `0001`–`0005` no Supabase.
2. Suba o worker (`python worker.py`) com a `service_role` no `.env`.
3. Na central (web), logado como admin/supervisor, abra **Relatório de OS** → **Executar**.
4. Acompanhe os logs ao vivo e baixe o `.txt` ao concluir.
