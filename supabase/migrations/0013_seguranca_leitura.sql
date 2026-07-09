-- ─────────────────────────────────────────────────────────────
-- 0013_seguranca_leitura.sql
-- Conserta a REGRESSÃO introduzida por 0010/0012.
--
-- O que quebrou: 0010/0012 passaram a exigir session_plena() (2FA/aal2 +
-- senha trocada) também no caminho de LEITURA. Isso derrubou o app real:
--
--   1) REALTIME morto → "resultado preso em Processando…"
--      O Supabase Realtime (postgres_changes de jobs/job_logs) reavalia a
--      policy de SELECT para entregar cada mudança, mas NÃO consegue avaliar
--      o claim 'aal' de forma confiável dentro dessa checagem. Com
--      session_plena() no SELECT, ele parou de entregar as atualizações →
--      o cartão do job fica preso em "Processando…" mesmo já concluído.
--
--   2) SSR / telas de admin vazias mesmo para admin COM 2FA
--      As páginas (index, sistema/[slug], avaliacoes, auditoria) fazem
--      `useAsyncData` no SSR, e os endpoints de admin leem com o token do
--      COOKIE. Esse token nem sempre está elevado a aal2 no servidor →
--      session_plena() falha lá → painel e telas de admin vêm vazios.
--      (Por isso é intermitente: rodar job na hora funciona — é client-side,
--       token aal2 em memória — mas reload/painel/admin vêm vazios.)
--
-- Decisão: a obrigatoriedade de 2FA continua imposta onde funciona de fato:
--   • no porteiro do app (middleware seguranca.global.ts), que já barra
--     qualquer usuário sem 2FA ANTES de qualquer página;
--   • na ÚNICA escrita que dispara automação — jobs_insert — que roda
--     client-side com o token já elevado (comprovado: os INSERTs de job dos
--     admins passaram normalmente). Ninguém RODA automação sem 2FA.
--
-- As LEITURAS voltam a depender só de cargo/propriedade (como era até o 0009),
-- restaurando realtime, SSR e as telas de admin.
--
-- MANTIDO da rodada de segurança: cadastro fail-closed (handle_new_user cria
-- usuário inativo — 0012) e a auditoria service_role-only (0011). Estes NÃO
-- são mexidos aqui.
--
-- ⚠️ Tradeoff consciente: reverter a leitura de giganet_reviews (PII de
-- cliente) e audit_log para is_admin() significa que um admin em aal1 (senha
-- sem o 2º fator) volta a conseguir lê-las via PostgREST direto. Como o 2FA
-- é exigido no login de todo mundo e essas telas são só-admin, o risco é
-- baixo para uma ferramenta interna. Se quiser blindar a PII de novo depois,
-- o caminho é reescrever avaliacoes.vue/auditoria.vue para ler client-side
-- (token aal2) e então repor session_plena() só nessas duas — sem quebrar
-- o realtime nem o SSR do resto.
-- ─────────────────────────────────────────────────────────────

-- ── systems: leitura por cargo (sem session_plena) ────────────
drop policy if exists systems_select on public.systems;
create policy systems_select on public.systems
  for select using (
    public.is_admin() or public.auth_role() = any (allowed_roles)
  );

-- escrita: só admin (sem session_plena — a trava de 2FA é o middleware)
drop policy if exists systems_admin_write on public.systems;
create policy systems_admin_write on public.systems
  for all using (public.is_admin()) with check (public.is_admin());

-- ── jobs ──────────────────────────────────────────────────────
-- SELECT volta ao modelo por propriedade → restaura o realtime.
drop policy if exists jobs_select on public.jobs;
create policy jobs_select on public.jobs
  for select using (public.is_admin() or requested_by = auth.uid());

-- DELETE: só admin (limpeza).
drop policy if exists jobs_admin_delete on public.jobs;
create policy jobs_admin_delete on public.jobs
  for delete using (public.is_admin());

-- INSERT: MANTÉM session_plena() — rodar automação exige 2FA concluído.
-- (roda client-side com token aal2; não quebra e bloqueia quem não tem 2FA,
--  inclusive na automação destrutiva "remover-linhas".)
drop policy if exists jobs_insert on public.jobs;
create policy jobs_insert on public.jobs
  for insert with check (
    public.session_plena()
    and requested_by = auth.uid()
    and exists (
      select 1 from public.systems s
      where s.slug = jobs.system_slug
        and s.kind = 'job'
        and s.active
        and (public.is_admin() or public.auth_role() = any (s.allowed_roles))
    )
  );

-- ── job_logs: leitura por propriedade do job → restaura logs ao vivo ──
drop policy if exists job_logs_select on public.job_logs;
create policy job_logs_select on public.job_logs
  for select using (
    exists (
      select 1 from public.jobs j
      where j.id = job_logs.job_id
        and (public.is_admin() or j.requested_by = auth.uid())
    )
  );

-- ── audit_log: leitura só admin ───────────────────────────────
drop policy if exists audit_admin_select on public.audit_log;
create policy audit_admin_select on public.audit_log
  for select using (public.is_admin());

-- ── profiles: próprio sempre; admin lê/gere todos ─────────────
drop policy if exists profiles_self_select on public.profiles;
create policy profiles_self_select on public.profiles
  for select using (id = auth.uid() or public.is_admin());

drop policy if exists profiles_admin_all on public.profiles;
create policy profiles_admin_all on public.profiles
  for all using (public.is_admin()) with check (public.is_admin());

-- ── giganet_reviews: leitura/gestão só admin (volta ao 0006) ──
drop policy if exists reviews_admin_read on public.giganet_reviews;
create policy reviews_admin_read on public.giganet_reviews
  for select using (public.is_admin());

drop policy if exists reviews_admin_update on public.giganet_reviews;
create policy reviews_admin_update on public.giganet_reviews
  for update using (public.is_admin()) with check (public.is_admin());

drop policy if exists reviews_admin_delete on public.giganet_reviews;
create policy reviews_admin_delete on public.giganet_reviews
  for delete using (public.is_admin());
-- (INSERT continua só via RPC webhook_inserir_avaliacao — security definer.)

-- ── storage 'resultados': admin ou dono do job (volta ao 0005) ──
drop policy if exists resultados_read on storage.objects;
create policy resultados_read on storage.objects
  for select to authenticated
  using (
    bucket_id = 'resultados'
    and (
      public.is_admin()
      or (storage.foldername(name))[1] in (
        select id::text from public.jobs where requested_by = auth.uid()
      )
    )
  );
