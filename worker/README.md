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
├─ agenda.py                 # rotina automática: sincroniza a Produção às 18h (ver §Agenda)
├─ config.py                 # .env + client Supabase (service_role)
├─ automacoes/               # adapters: slug → chama o script e monta o Resultado
│  ├─ base.py                # BaseAutomacao / Resultado / Arquivo
│  ├─ runner.py              # subprocess (log ao vivo) + carregar_script (importlib)
│  ├─ registry.py            # slug → automação
│  └─ *.py                   # um adapter por sistema (relatorio_os, termos, …)
├─ scripts_originais/        # código das automações (repo automacoes-main)
│  ├─ comum/                 # módulos compartilhados: sgp_api, focus_api, sgp_login
│  ├─ relatorios/            # main.py (Relatório de OS), termos_agendados.py, producao_os.py
│  ├─ vendas/                # vendas_focus_sgp.py (Verificar Vendas)
│  ├─ telefonia/             # relatorio_linhas_canceladas.py, remover_linhas.py
│  └─ conferencia-os/        # checklist_equipe.py (engine da Conferência)
├─ monitor/                  # API HTTP do Monitor de Rede (roda em thread; ver §Monitor)
│  ├─ service.py             # Flask (/api/snapshot, /api/pon) + iniciar_em_thread
│  ├─ smartolt_api.py        # cliente SmartOLT (X-Token)
│  ├─ sgp_api.py             # cliente SGP (Token/App)
│  ├─ cruza_sgp.py           # cruza ONU (SmartOLT) × cliente (SGP)
│  └─ demo_data.py           # dados fictícios (MONITOR_DEMO=1)
├─ requirements.txt
├─ .env.example
└─ deploy/worker.service
```

## Como as credenciais são usadas

| Automação | Acesso | Credenciais |
|---|---|---|
| Relatório de OS, Termos Agendados | SGP API (URA) | `SGP_TOKEN` / `SGP_APP` |
| Produção (dashboard + rotina das 18h) | SGP API (URA) | `SGP_TOKEN` / `SGP_APP` |
| Verificar Vendas | FocusChat API + SGP API | `FOCUS_TOKENS` (vários canais, vírgula) ou `FOCUS_TOKEN` (1 só), `SGP_TOKEN` / `SGP_APP` |
| Conferência de Checklist | SGP login web | `SGP_USER` / `SGP_PASS` |
| Linhas Canceladas, Remover Linhas | SGP login web (+ Chromium) | `SGP_USER` / `SGP_PASS` |
| Monitor de Rede | SmartOLT API + SGP API | `SMARTOLT_SUBDOMAIN` / `SMARTOLT_TOKEN`, `SGP_TOKEN` / `SGP_APP` |

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

## Agenda: Produção às 18h (rotina automática)

Além da fila, o worker sobe uma thread (`agenda.py`) que **todo dia às 18h de
Brasília** — horário em que o técnico encerra o expediente — lê no SGP as OS
finalizadas e grava na tabela `os_producao`, que alimenta o painel **Produção**
da Central (`/producao`).

```
[agenda] produção agendada para 18:00 (Brasília) · última execução: 10/08/2026
[agenda] sincronizando a produção (janela de 3 dia(s))…
[agenda] produção atualizada: 214 OS gravadas (rotina das 18:00).
```

- **Janela de 3 dias, não só hoje**: OS de plantão são encerradas depois das 18h
  e às vezes o técnico lança no dia seguinte. O upsert é por `os_id`, então
  reprocessar dias já sincronizados corrige o passado sem duplicar nada.
- **Worker fora do ar às 18h?** Ao subir, ele consulta `os_sync`; se o dia ainda
  não foi sincronizado e já passou do horário, roda na hora — um deploy no meio
  da tarde não deixa buraco no dashboard.
- **SGP fora do ar às 18h?** Tenta de novo a cada 15 min, até 4 vezes, antes de
  desistir do dia. O erro fica em `os_sync` e o painel avisa que os dados estão
  velhos (banner amarelo depois de 36h sem sincronização).
- **Backfill / reprocessar**: a automação **Sincronizar Produção**
  (`producao-sync`) na Central aceita um período (`de`/`até`) e faz o mesmo
  trabalho sob demanda. Um mês inteiro (~1.200 OS) leva ~10s.
- Configuração: `PRODUCAO_SYNC_ENABLED`, `PRODUCAO_SYNC_HORA` (padrão `18:00`),
  `PRODUCAO_SYNC_DIAS` (padrão `3`). Desligar: `PRODUCAO_SYNC_ENABLED=false`.
- Teste avulso, sem esperar o horário: `python -m agenda`.

> Requer a migration `0016_producao.sql` aplicada (cria `os_producao`, `os_sync`,
> a RPC do painel e cadastra os dois sistemas).

## Monitor de Rede (API embarcada)

O worker também sobe, **numa thread**, a API do Monitor de Rede (o painel em
tempo real da Central, só admin/supervisor) — não precisa de outro processo. No
arranque aparece:

```
[worker] monitor SmartOLT em http://127.0.0.1:5001 (API p/ a Central)
```

- Endpoints: `GET /api/snapshot` e `GET /api/pon?olt=&board=&port=&janela=`.
- A Central (web) consome via `web/server/api/monitor/*` (proxy que exige o
  cargo), apontando `MONITOR_API_URL` (em `web/.env`) para este `host:porta`.
- Credenciais: `SMARTOLT_*` + `SGP_TOKEN`/`SGP_APP` no `.env` (as do SGP já são
  as mesmas das outras automações).
- Desligar: `MONITOR_API_ENABLED=false`. Testar sem credenciais: `MONITOR_DEMO=1`.
- **Web em outro host** (ex.: Vercel, com o worker no VPS): defina o mesmo
  `MONITOR_API_TOKEN` aqui e em `web/.env`, e `MONITOR_HOST=0.0.0.0` — a API
  passa a exigir o header `X-Monitor-Token`.

Teste isolado do monitor (sem a fila): `MONITOR_DEMO=1 python -m monitor.service`.

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
