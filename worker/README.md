# Worker — Central Giganet

Processo Python que observa a fila de `jobs` no Supabase, executa a automação
correspondente (reaproveitando os scripts de `scripts_originais/`) e grava
logs ao vivo + resultado de volta.

> A maioria das automações agora usa **API oficial** do SGP (Token/App, sem 2FA)
> e do FocusChat (Token do Canal). Só **Remover Linhas** precisa de Chromium
> (Playwright) — por isso o worker roda no seu PC, num VPS ou no easypanel, não
> em serverless. A `service_role` key fica **só aqui**.

## Estrutura

```
worker/
├─ worker.py                 # loop: claim_next_job → executa → grava resultado
├─ config.py                 # .env + client Supabase (service_role)
├─ automacoes/               # adapters: slug → chama o script e monta o Resultado
│  ├─ base.py                # BaseAutomacao / Resultado / Arquivo
│  ├─ runner.py              # subprocess (log ao vivo) + carregar_script (importlib)
│  ├─ registry.py            # slug → automação
│  └─ *.py                   # um adapter por sistema (relatorio_os, termos, …)
├─ scripts_originais/        # código das automações (repo automacoes-main)
│  ├─ comum/                 # módulos compartilhados: sgp_api, focus_api, sgp_login
│  ├─ relatorios/            # main.py (Relatório de OS), termos_agendados.py
│  ├─ vendas/                # vendas_focus_sgp.py (Verificar Vendas)
│  ├─ telefonia/             # relatorio_linhas_canceladas.py, remover_linhas.py
│  └─ conferencia-os/        # checklist_equipe.py (engine da Conferência)
├─ requirements.txt
├─ .env.example
└─ deploy/worker.service
```

## Como as credenciais são usadas

| Automação | Acesso | Credenciais |
|---|---|---|
| Relatório de OS, Termos Agendados | SGP API (URA) | `SGP_TOKEN` / `SGP_APP` |
| Verificar Vendas | FocusChat API + SGP API | `FOCUS_TOKEN`, `SGP_TOKEN` / `SGP_APP` |
| Conferência de Checklist | SGP login web | `SGP_USER` / `SGP_PASS` |
| Linhas Canceladas, Remover Linhas | SGP login web (+ Chromium) | `SGP_USER` / `SGP_PASS` |

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
