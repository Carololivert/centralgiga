# Central de Automações Giganet — Prompt para Claude Code (Nuxt + Supabase + Worker Python)

> Cole este prompt no Claude Code na pasta do projeto. Antes de colar, preencha os trechos marcados com 🔧.

---

Quero que você construa uma **central web interna** para a Giganet (provedor de internet) que reúne 4 sistemas de automação escritos em **Python** num único painel, com **controle de acesso por cargo (RBAC)**. O frontend e a autenticação ficam em **Nuxt 4 + Supabase**, e as automações continuam em **Python**, rodando por um worker.

## 1. Contexto e objetivo

- A Giganet **já tem uma central compartilhada** rodando esses 4 scripts Python de automação hoje. Quero criar uma **nova central separada** (esta), agora com login e controle de acesso por cargo — a central atual continua existindo; esta é paralela.
- Cada usuário só vê e executa os sistemas que o cargo dele permite.
- A central atual está em `🔧 [caminho/repo da central que já existe]` e os scripts em `🔧 [caminho dos scripts]`. **Antes de começar, leia a central atual e os scripts** para entender como cada automação já é invocada hoje (argumentos, entradas, saídas e dependências como Playwright/requests e login no SGP) e **replique essa mesma lógica de execução** no worker — sem reinventar.
- Já uso Nuxt + Supabase + Nuxt UI v4 em outro projeto; quero o mesmo padrão aqui.

## 2. Arquitetura

Três peças:

1. **App Nuxt 4** — UI + login (Supabase Auth). Mostra os sistemas por cargo, dispara execuções e acompanha status/logs ao vivo.
2. **Supabase** — Postgres (usuários, cargos, fila de jobs, logs, resultados), Auth, RLS (permissões), Realtime (status ao vivo) e Storage (arquivos de resultado).
3. **Worker Python** — processo que observa a fila de jobs no Supabase, executa a automação Python correspondente e grava logs/resultado de volta.

### Fluxo de uma execução
1. Usuário loga no Nuxt (Supabase Auth).
2. Dashboard mostra **só os sistemas permitidos** para o cargo dele.
3. Ao clicar **Executar**, o Nuxt insere uma linha em `jobs` com status `na_fila`. A **RLS garante** que só quem tem permissão naquele sistema consegue inserir.
4. O **worker Python** (rodando onde o Playwright funciona) reivindica o job (`executando`), roda a automação (adapter do script existente) e grava os logs em `job_logs` em tempo real.
5. Ao terminar, grava o resultado (CSV/Excel) no **Supabase Storage**, preenche `result_path` e marca o job como `concluido` (ou `erro`, com a mensagem).
6. O Nuxt acompanha tudo ao vivo por **Supabase Realtime** (status + logs) e oferece o **download** do resultado.

> ⚠️ Importante: o worker Python precisa rodar **onde o Playwright/Chromium roda** (meu PC ou um VPS) — não no Vercel nem em Edge Functions do Supabase. A `service_role key` do Supabase fica **só no worker**, nunca no frontend.

## 3. Stack

- **Frontend:** Nuxt 4 + `@nuxtjs/supabase` + **Nuxt UI v4** + TypeScript.
- **Backend/dados:** Supabase (Postgres + Auth + RLS + Realtime + Storage).
- **Automações:** Python + `supabase-py` (worker), mantendo os scripts atuais (Playwright/requests).
- **Migrations:** SQL versionado na pasta `supabase/migrations` (aplicável via Supabase CLI ou SQL Editor).

## 4. Hierarquia de usuários (RBAC)

Três cargos:

| Cargo | Acesso |
|---|---|
| **Admin** | Tudo: os 4 sistemas + gestão de usuários + auditoria |
| **Supervisor** | Apenas: Verificar Vendas + Verificar Números |
| **Atendente** | Apenas: Conferência de OS |

Implementação:
- Tabela `profiles` (1:1 com `auth.users`) com coluna `role` (`admin`/`supervisor`/`atendente`) e `active`.
- Função auxiliar `auth_role()` (`security definer`, lê o `role` do `profiles` do usuário logado) para usar nas policies — assim evita recursão de RLS.
- A permissão de cada sistema vem da tabela `systems` (coluna `allowed_roles text[]`) — **nada de permissão hardcoded espalhada**.
- No Nuxt: middleware `auth` (exige login) e `role` (checa o cargo exigido pela rota). O dashboard lista só os sistemas cujo `allowed_roles` contém o cargo do usuário.

## 5. Os 4 sistemas

🔧 Confirme/ajuste nomes e descrições conforme meus scripts reais:

1. **Verificar Vendas** — 🔧 [ex. cruza dados do FocusChat com o SGP para achar vendas/leads não cadastrados] — cargos: `admin`, `supervisor`.
2. **Verificar Números** — 🔧 [ex. identifica e remove números de contratos de telefonia cancelados no SGP] — cargos: `admin`, `supervisor`.
3. **Conferência de OS** — 🔧 [ex. confere as ordens de serviço ...] — cargos: `admin`, `atendente`.
4. **🔧 [Sistema 4 — nome e descrição]** — cargos: 🔧 [defina].

## 6. Modelo de dados (Supabase / Postgres)

Crie as migrations com estas tabelas e regras:

- `profiles` — `id` (FK `auth.users`), `full_name`, `role`, `active`, `created_at`.
- `systems` — `id`, `slug` (único), `name`, `description`, `allowed_roles text[]`.
- `jobs` — `id`, `system_slug`, `requested_by` (FK `auth.users`), `status` (`na_fila`/`executando`/`concluido`/`erro`), `params jsonb`, `error text`, `result_path text`, `created_at`, `started_at`, `finished_at`.
- `job_logs` — `id`, `job_id` (FK `jobs`), `level`, `line`, `created_at` (para o log ao vivo).
- `audit_log` — `id`, `user_id`, `action`, `detail jsonb`, `created_at` (ações de admin, ex. criação/edição de usuário).

RLS (resumo da intenção):
- `profiles`: usuário lê o próprio; admin lê/escreve todos.
- `systems`: leitura só dos sistemas cujo `allowed_roles` contém `auth_role()`; escrita só admin.
- `jobs`: **insert** permitido só se o `allowed_roles` do `system_slug` contém `auth_role()`. **Select**: admin vê todos; demais veem os próprios jobs.
- `job_logs`: select acompanha a visibilidade do job pai.
- O **worker** usa a `service_role key` e ignora RLS (correto para backend).

RPC para a fila (atomicidade):
- Crie uma função `claim_next_job()` (`security definer`) que faz o dequeue com `FOR UPDATE SKIP LOCKED`, marca como `executando`, seta `started_at` e retorna o job. O worker chama via `rpc('claim_next_job')` — evita dois processamentos do mesmo job.

Realtime:
- Habilite Realtime (publication) nas tabelas `jobs` e `job_logs` para o Nuxt assinar status e logs.

## 7. Worker Python

- `worker/worker.py`: loop que chama `claim_next_job()` (polling a cada poucos segundos; pode evoluir pra Realtime depois), executa a automação e grava de volta.
- `worker/automacoes/base.py`: classe base `BaseAutomacao` com metadados (`slug`, `nome`, `descricao`, `cargos`, `parametros`) e método `run(params, log)`, onde `log(linha, nivel)` insere em `job_logs` em tempo real.
- Para cada sistema, um **adapter** que importa/chama o script original **sem reescrever a lógica** (refatore só o mínimo para expor uma função executável).
- `registry.py`: registra todas as automações; o worker resolve a automação pelo `system_slug` do job.
- Ao concluir: gera o resultado (CSV/Excel), faz **upload no Supabase Storage** (bucket privado), salva `result_path`, marca `concluido`. Em falha: marca `erro` e grava a mensagem.
- Deploy: incluir um `deploy/worker.service` (systemd) e instruções pra rodar no VPS (instalar dependências do Playwright/Chromium).

## 8. Frontend Nuxt

Páginas:
- `login.vue` — login Supabase.
- `index.vue` — dashboard com cards dos sistemas permitidos (Nuxt UI v4).
- `sistema/[slug].vue` — formulário de parâmetros (se houver), botão **Executar** (insere job), **status e logs ao vivo** (assinatura Realtime de `jobs` + `job_logs`), histórico de execuções e **download do resultado**.
- `usuarios.vue` — só admin: criar, editar, ativar/desativar e atribuir cargo.
- `auditoria.vue` — só admin: quem executou o quê e quando.

Outros:
- Middleware `auth` e `role`; composable `useRole()` lendo o `role` do `profiles`.
- `.env.example` com `SUPABASE_URL` e `SUPABASE_KEY` (anon). **Nunca** a service_role aqui.
- Visual limpo e profissional, com a identidade da Giganet (azul).

## 9. Segurança

- Senhas geridas pelo Supabase Auth (hash nativo).
- RLS ativa em todas as tabelas.
- `service_role key` só no worker; no frontend só a anon key.
- Bucket de resultados **privado**; download por **signed URL**.
- Credenciais do SGP e afins só no `.env` do worker (inclua `.env.example`).

## 10. Estrutura sugerida

```
giganet-central/
  web/                       # Nuxt 4 + @nuxtjs/supabase + Nuxt UI v4
    pages/  middleware/  composables/  nuxt.config.ts  .env.example
  worker/                    # Worker Python
    worker.py
    automacoes/  base.py  registry.py  vendas/  numeros/  os/  sistema4/
    scripts_originais/       # 🔧 meus scripts atuais
    requirements.txt  .env.example  deploy/worker.service
  supabase/
    migrations/  0001_schema.sql  0002_rls.sql  0003_rpc.sql  0004_seed.sql
  README.md
```

## 11. Critérios de aceite

- [ ] Login com Supabase Auth funcionando, com os 3 cargos.
- [ ] RLS aplicada: usuário só insere job de sistema permitido ao cargo dele.
- [ ] Dashboard mostra só os sistemas permitidos por cargo.
- [ ] Os 4 sistemas Python integrados via adapter e executáveis pela interface.
- [ ] Worker reivindica jobs da fila sem duplicar (via `claim_next_job`).
- [ ] Status e logs ao vivo no Nuxt via Realtime.
- [ ] Resultados em CSV/Excel salvos no Storage e baixáveis (signed URL).
- [ ] Admin gerencia usuários e vê a auditoria.
- [ ] README com setup (Supabase, Nuxt, worker no VPS) e nenhuma credencial hardcoded.

## 12. Como conduzir o trabalho

1. Primeiro, **leia a central atual e os scripts** em `🔧 [caminho]` e me diga como cada automação já é chamada hoje (inputs/outputs). A nova central deve **reaproveitar essa lógica de execução**, só envolvendo num adapter.
2. Me pergunte o que faltar (parâmetros de cada automação, se quero agendamento recorrente) **antes** de codar.
3. Construa de forma **incremental** e valide comigo em cada etapa:
   1. Migrations do Supabase (schema + RLS + `claim_next_job` + seed dos systems).
   2. Nuxt: login + dashboard com gating por cargo (sem automação ainda).
   3. Worker: esqueleto que reivindica job + **um** sistema rodando ponta a ponta (com logs e resultado).
   4. Integrar os demais sistemas.
   5. Exportação de resultados + auditoria + tela de usuários.
4. Ao fim de cada etapa, mostre o que fez e como testar.
