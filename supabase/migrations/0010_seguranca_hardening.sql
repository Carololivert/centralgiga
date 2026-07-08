-- ─────────────────────────────────────────────────────────────
-- 0010_seguranca_hardening.sql
-- Fecha brechas encontradas na revisão de segurança do login/2FA:
--
--  (A) A obrigatoriedade de 2FA e de troca de senha provisória estava
--      SÓ no middleware do cliente (UX). Uma sessão AAL1 chamando o
--      PostgREST direto (com o próprio JWT) contornava tudo. Agora a
--      trava vive na RLS (camada de dados): systems/jobs/job_logs/audit
--      exigem sessão "plena" = 2FA concluído (aal2) + senha já trocada.
--
--  (B) O trigger handle_new_user copiava profiles.role do metadata do
--      usuário, que é controlável via signup público (anon key). Isso
--      permitia auto-promoção a admin. Agora o trigger SEMPRE cria como
--      'atendente'; o cargo real é definido no servidor (index.post.ts).
-- ─────────────────────────────────────────────────────────────

-- ── (A) Sessão "plena": 2FA concluído + perfil ativo + senha trocada ──
create or replace function public.session_plena()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select
    coalesce(auth.jwt() ->> 'aal', 'aal1') = 'aal2'
    and exists (
      select 1
      from public.profiles
      where id = auth.uid()
        and active = true
        and must_change_password = false
    )
$$;

comment on function public.session_plena() is
  'true quando a sessão concluiu o 2FA (aal2) e o usuário já trocou a senha provisória. Usada nas policies para exigir onboarding completo antes de acessar dados.';

-- ── systems: leitura exige sessão plena ───────────────────────
drop policy if exists systems_select on public.systems;
create policy systems_select on public.systems
  for select using (
    public.session_plena()
    and (public.is_admin() or public.auth_role() = any (allowed_roles))
  );

-- ── jobs: enfileirar e listar exigem sessão plena ─────────────
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

drop policy if exists jobs_select on public.jobs;
create policy jobs_select on public.jobs
  for select using (
    public.session_plena()
    and (public.is_admin() or requested_by = auth.uid())
  );

-- (DELETE de jobs continua só admin; mantém a policy existente.)

-- ── job_logs: leitura exige sessão plena ──────────────────────
drop policy if exists job_logs_select on public.job_logs;
create policy job_logs_select on public.job_logs
  for select using (
    public.session_plena()
    and exists (
      select 1 from public.jobs j
      where j.id = job_logs.job_id
        and (public.is_admin() or j.requested_by = auth.uid())
    )
  );

-- ── audit_log: leitura (admin) exige sessão plena ─────────────
drop policy if exists audit_admin_select on public.audit_log;
create policy audit_admin_select on public.audit_log
  for select using (public.session_plena() and public.is_admin());

-- Nota: profiles_self_select NÃO recebe session_plena — o próprio
-- middleware/perfil precisa ler o profile em AAL1 para saber que ainda
-- falta trocar a senha / cadastrar o 2FA. Isso é seguro: o usuário só
-- enxerga o próprio profile.

-- ── (B) Trigger: nunca confiar no role vindo do metadata ──────
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, full_name, role)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', split_part(new.email, '@', 1)),
    'atendente'  -- SEMPRE atendente; o cargo real é definido no servidor (admin).
  )
  on conflict (id) do nothing;
  return new;
end $$;
