# Central de Automações Giganet

Central web interna que reúne as automações da Giganet num painel único, com **login e controle de acesso por cargo (RBAC)**. Roda paralela à central atual (`../Lista`), que continua existindo.

- **Frontend + Auth:** Nuxt 4 + `@nuxtjs/supabase` + Nuxt UI v4
- **Dados:** Supabase (Postgres + Auth + RLS + Realtime + Storage) — **reusa o projeto da central atual**
- **Automações:** Python (worker), reaproveitando os scripts do `../Lista/Aut-SGP`

## Sistemas e cargos

| Sistema | Origem | Tipo | Cargos |
|---|---|---|---|
| **Relatório de OS** | `Aut-SGP/main.py` | fila | admin, supervisor |
| **Termos Agendados** | `Aut-SGP/termos_agendados.py` | fila | admin, supervisor |
| **Conferência de Checklist** | `Aut-SGP/checklist_equipe.py` (IA) | fila | admin, atendente |
| **Giganet Avaliações** | central antiga + n8n | inbox (aprovação) | admin |

> Decisões desta central: a **Folha de Pagamento** ficou de fora (não é SGP/Giganet); **Avaliações** é portada pra cá reusando o n8n e a tabela `giganet_reviews`; **Supabase** é o mesmo projeto da central atual.

## Arquitetura

```
Centralgiga/
  web/                 # Nuxt 4 (UI + Auth + API routes das avaliações)
  worker/              # Worker Python (fila → executa → Storage)
  supabase/migrations/ # SQL versionado (rode no SQL Editor ou via CLI)
  README.md
```

Fluxo de uma execução (sistemas de fila): o usuário clica **Executar** → o Nuxt insere uma linha em `jobs` (a **RLS** só deixa se o cargo tiver acesso) → o **worker Python** reivindica o job (`claim_next_job`), roda o script e grava logs em `job_logs` e o resultado no **Storage** → o Nuxt acompanha por **Realtime** e oferece o download por **signed URL**.

`service_role` fica **só no worker**. O frontend usa só a `anon key` + a sessão do usuário (RLS).

---

## Etapa 1 — Banco (Supabase)

Rode as migrations **na ordem**, no SQL Editor do projeto Supabase (o mesmo da central atual):

1. `supabase/migrations/0001_schema.sql` — tabelas `profiles`, `systems`, `jobs`, `job_logs`, `audit_log` + trigger de profile + Realtime
2. `0002_rls.sql` — helpers `auth_role()`/`is_admin()` + políticas RLS
3. `0003_rpc.sql` — `claim_next_job()` (fila) e `registrar_auditoria()`
4. `0004_seed.sql` — catálogo dos 4 sistemas
5. `0005_storage.sql` — bucket privado `resultados` + policy de leitura
6. `0006_avaliacoes.sql` — **⚠️ cutover das avaliações** (liga RLS no `giganet_reviews` e cria a RPC do webhook). Rode **só** quando for migrar as avaliações — isso desativa o módulo giganet da central antiga e exige reapontar o webhook do n8n. **Troque o valor de `app_secrets.giganet_webhook_secret`.**

### Criar o primeiro usuário (admin)

1. No painel do Supabase: **Authentication → Users → Add user** (com e-mail e senha).
2. O trigger cria o `profiles` automaticamente como `atendente`. Promova a admin no SQL Editor:
   ```sql
   update public.profiles set role = 'admin'
   where id = (select id from auth.users where email = 'voce@giganet.com');
   ```

### Como testar a Etapa 1
```sql
-- deve listar os 4 sistemas
select slug, name, allowed_roles, kind from public.systems order by sort_order;
-- deve existir e retornar o seu cargo (rode logado via app; no SQL editor volta null)
select public.auth_role();
```

---

## Etapa 2 — App Nuxt (login + dashboard com gating)

```bash
cd web
cp .env.example .env      # preencha SUPABASE_URL e SUPABASE_KEY (anon)
npm install
npm run dev               # http://localhost:3000
```

> `SUPABASE_URL` / `SUPABASE_KEY` são os mesmos da central atual (a `anon key`).
> No `Lista/.env.local` eles aparecem como `NEXT_PUBLIC_SUPABASE_URL` / `SUPABASE_ANON_KEY`.

### Como testar a Etapa 2
- Abrir `http://localhost:3000` sem login → redireciona pra `/login`.
- Entrar com o usuário criado.
  - **Admin:** vê os 4 cards + menu **Usuários** e **Auditoria**.
  - **Supervisor:** vê só **Relatório de OS** e **Termos Agendados**.
  - **Atendente:** vê só **Conferência de Checklist**.
- Tentar abrir `/usuarios` ou `/avaliacoes` como não-admin → **403**.
- O dashboard lista os sistemas vindos do banco (RLS filtra por cargo); a execução em si chega na Etapa 3.

---

## Etapa 3 — Worker Python + execução ponta a ponta

O worker (`worker/`) reivindica jobs (`claim_next_job`), executa a automação e
grava logs ao vivo + resultado no Storage. Nesta etapa vai **um** sistema ponta
a ponta: **Relatório de OS** (`scripts_originais/main.py`). A tela
`web/app/pages/sistema/[slug].vue` insere o job, acompanha status + logs por
**Realtime** e baixa o resultado por **signed URL**.

```bash
cd worker
python -m venv venv && venv\Scripts\activate     # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
# edite worker/.env: preencha SUPABASE_SERVICE_ROLE_KEY (Settings → API → service_role)
python worker.py
```

### Como testar a Etapa 3
1. Migrations `0001`–`0005` aplicadas (a `0003` concede `claim_next_job` à `service_role`).
2. `worker.py` rodando com a `service_role` no `.env` (SGP já preenchido).
3. Na central (logado como admin/supervisor) → **Relatório de OS** → **Executar**.
4. O status sai de `na_fila` → `executando` → `concluido`, os logs aparecem ao
   vivo e o `.txt` fica disponível pra download. Detalhes em `worker/README.md`.

> Sem o worker rodando, o job fica em `na_fila` (é o esperado).

## Etapa 4 — demais sistemas (Termos + Checklist)

Os três sistemas de fila estão integrados no worker (`worker/automacoes/registry.py`):

- **Termos Agendados** → texto na tela (Copiar / Baixar .txt).
- **Conferência de Checklist** → **painel estruturado** por OS (status ok/atenção/problema,
  problemas expansíveis, alerta de MAC, localização). Recebe o parâmetro `equipe`. O JSON
  completo vai pro Storage (.json); o resumo estruturado é exibido na tela.

> O checklist roda a 2ª opinião com IA só quando as regras locais já acham "problema".
> Para ligar essa análise, preencha `ANTHROPIC_API_KEY` no `worker/.env`
> (sem ela, as regras locais continuam funcionando).

## Próximas etapas

- **Etapa 5:** módulo de Avaliações (inbox + webhook + n8n), gestão de usuários e auditoria.
