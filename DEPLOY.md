# Deploy — Central de Automações Giganet

Três peças:

| Peça | Onde | Por quê |
|---|---|---|
| **web** (Nuxt 4) | **Vercel** | front + API routes (avaliações). Serverless. |
| **worker** (Python + Playwright) | **easypanel** (Docker) ou **VPS** | Remover Linhas usa Chromium → não roda em serverless. |
| **banco** (Supabase) | já configurado | nada a fazer (migrations 0001–0006 aplicadas). |

> Os valores das variáveis estão nos seus arquivos locais `web/.env` e `worker/.env`.
> **Nunca** comite `.env` (já está no `.gitignore`).

---

## 1. Web na Vercel

A central web está na subpasta **`web/`**.

### Variáveis de ambiente (Vercel → Project → Settings → Environment Variables)
```
SUPABASE_URL            = https://SEU-PROJETO.supabase.co
SUPABASE_KEY            = (anon key — web/.env)
SUPABASE_SERVICE_KEY    = (service_role — web/.env)   ← só no servidor, nunca exposta
GIGANET_WEBHOOK_SECRET  = (web/.env)
N8N_PUBLICAR_URL        = https://SEU-N8N.exemplo.com/webhook/giganet-publicar
N8N_REGERAR_URL         = https://SEU-N8N.exemplo.com/webhook/giganet-regerar
ANTHROPIC_API_KEY       = (opcional — botão "regerar" usa o n8n, não precisa)
ANTHROPIC_MODEL         = claude-sonnet-4-6
NUXT_PUBLIC_SGP_URL     = https://SEU-AUT-SGP.exemplo.com
# Monitor de Rede (proxy em /api/monitor/*) → aponta pro worker no easypanel:
MONITOR_API_URL         = https://SEU-MONITOR.easypanel.host   (domínio do worker, porta 5001)
MONITOR_API_TOKEN       = (mesmo segredo do worker — protege o endpoint exposto)
```

### Passo a passo
1. Suba o repositório no GitHub (veja "Git" abaixo) e em **vercel.com → Add New Project → Import** o repo.
2. **Root Directory: `web`** (importante — o app não está na raiz). O Nuxt é detectado sozinho (build `nuxt build`, sem config extra).
3. Cole as variáveis acima (Production).
4. **Deploy.** Anote a URL (ex.: `https://central-giganet.vercel.app`).

> Alternativa por CLI: `npm i -g vercel`, depois dentro de `web/`: `vercel` (link) e `vercel --prod`.

---

## 2. Worker no easypanel (Docker)

O worker tem um **`Dockerfile`** pronto (Python + Chromium do Playwright).

1. easypanel → **Create → App → Source: o repositório**, **Build: Dockerfile**, **Build context / path: `worker`**.
2. Variáveis de ambiente do serviço:
   ```
   SUPABASE_URL               = https://SEU-PROJETO.supabase.co
   SUPABASE_SERVICE_ROLE_KEY  = (worker/.env)
   RESULT_BUCKET              = resultados
   # SGP via API oficial (Token/App) — Relatório de OS, Termos, Verificar Vendas:
   SGP_BASE                   = https://giganetwireless.sgp.net.br
   SGP_TOKEN                  = (worker/.env)
   SGP_APP                    = (worker/.env)
   # SGP via login web — Conferência de Checklist, Linhas Canceladas, Remover Linhas:
   SGP_USER                   = (worker/.env)
   SGP_PASS                   = (worker/.env)
   SGP_VERIFY_SSL             = false
   SGP_2FA_SECRET             = (worker/.env)   # segredo TOTP, se o login web exigir 2FA
   # FocusChat via API oficial (Token do Canal) — Verificar Vendas:
   FOCUS_TOKEN                = (worker/.env)
   WORKER_POLL_SECONDS        = 5
   # SmartOLT (Monitor de Rede) — temperatura/outage das OLTs:
   SMARTOLT_SUBDOMAIN         = (worker/.env)
   SMARTOLT_TOKEN             = (worker/.env)
   # Monitor: no container já escuta em 0.0.0.0 (default da imagem). Proteja o
   # endpoint exposto com um segredo forte (o MESMO valor na Vercel):
   MONITOR_API_TOKEN          = (gere um segredo forte)
   ```
3. **Exponha a porta do Monitor:** em **Domains** do app, adicione um domínio apontando para a **porta 5001** (o easypanel provisiona HTTPS sozinho). Essa URL vira o `MONITOR_API_URL` na Vercel. As automações continuam só de saída — o único inbound é a API do monitor, protegida pelo `MONITOR_API_TOKEN`. Deixe **restart: always**.
4. Deploy. Nos logs deve aparecer `[worker] iniciado · automações: relatorio-os, termos-agendados, ...`.

### Alternativa: VPS com systemd
Use `worker/deploy/worker.service` (instruções no `worker/README.md`): `python -m venv`, `pip install -r requirements.txt`, `playwright install chromium`, preencher `.env`, `systemctl enable --now giganet-worker`.

---

## 3. Pós-deploy

1. **Reapontar o n8n** (fecha o "gap" das avaliações): no fluxo que envia as avaliações novas, troque a URL para a da Vercel:
   - `POST https://SEU-DOMINIO.vercel.app/api/avaliacoes/webhook`
   - header `x-webhook-secret: <GIGANET_WEBHOOK_SECRET>`
2. **Teste o login** na URL da Vercel (admin `rafael@gmail.com`). Crie usuários em **Usuários**.
3. **Teste um job** (Relatório de OS → Executar) — confirma que o worker no easypanel está pegando a fila.
4. **Avaliações** — as 51 existentes aparecem; novas passam a chegar pelo n8n reapontado.

---

## Git (para o deploy via GitHub)

A pasta `Centralgiga` ainda não é um repositório. Para subir:
```bash
cd Centralgiga
git init
git add .
git commit -m "Central Giganet — web + worker + supabase"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/centralgiga.git
git push -u origin main
```
O `.gitignore` já protege os `.env`, `node_modules`, `venv`, `.nuxt`, etc.

---

## Segurança (resumo)
- `service_role` só no **worker** e nas **server routes** do web (nunca no navegador).
- Bucket `resultados` privado (download por signed URL).
- `.env` nunca vai pro git.
- Avaliações: tabela com RLS; webhook protegido por `x-webhook-secret` + RPC com segredo.
