-- ─────────────────────────────────────────────────────────────
-- 0002_rls.sql · Helpers de cargo + Row Level Security
-- ─────────────────────────────────────────────────────────────

-- ── Helpers (security definer para evitar recursão de RLS) ────
create or replace function public.auth_role()
returns public.user_role
language sql stable security definer set search_path = public
as $$
  select role from public.profiles where id = auth.uid() and active = true
$$;

create or replace function public.is_admin()
returns boolean
language sql stable security definer set search_path = public
as $$
  select coalesce(public.auth_role() = 'admin', false)
$$;

-- ── profiles ──────────────────────────────────────────────────
alter table public.profiles enable row level security;

drop policy if exists profiles_self_select on public.profiles;
create policy profiles_self_select on public.profiles
  for select using (id = auth.uid() or public.is_admin());

drop policy if exists profiles_admin_all on public.profiles;
create policy profiles_admin_all on public.profiles
  for all using (public.is_admin()) with check (public.is_admin());

-- ── systems ───────────────────────────────────────────────────
alter table public.systems enable row level security;

-- leitura: admin vê tudo; demais só os sistemas do seu cargo
drop policy if exists systems_select on public.systems;
create policy systems_select on public.systems
  for select using (
    public.is_admin() or public.auth_role() = any (allowed_roles)
  );

-- escrita: só admin
drop policy if exists systems_admin_write on public.systems;
create policy systems_admin_write on public.systems
  for all using (public.is_admin()) with check (public.is_admin());

-- ── jobs ──────────────────────────────────────────────────────
alter table public.jobs enable row level security;

-- INSERT permitido só se o sistema (kind='job', ativo) permite o cargo do usuário
-- e o job é registrado em nome do próprio usuário.
drop policy if exists jobs_insert on public.jobs;
create policy jobs_insert on public.jobs
  for insert with check (
    requested_by = auth.uid()
    and exists (
      select 1 from public.systems s
      where s.slug = jobs.system_slug
        and s.kind = 'job'
        and s.active
        and (public.is_admin() or public.auth_role() = any (s.allowed_roles))
    )
  );

-- SELECT: admin vê todos; demais veem os próprios
drop policy if exists jobs_select on public.jobs;
create policy jobs_select on public.jobs
  for select using (public.is_admin() or requested_by = auth.uid());

-- DELETE: só admin (limpeza)
drop policy if exists jobs_admin_delete on public.jobs;
create policy jobs_admin_delete on public.jobs
  for delete using (public.is_admin());

-- (UPDATE dos jobs é feito pelo worker com a service_role, que ignora RLS.)

-- ── job_logs ──────────────────────────────────────────────────
alter table public.job_logs enable row level security;

drop policy if exists job_logs_select on public.job_logs;
create policy job_logs_select on public.job_logs
  for select using (
    exists (
      select 1 from public.jobs j
      where j.id = job_logs.job_id
        and (public.is_admin() or j.requested_by = auth.uid())
    )
  );

-- (INSERT de logs é feito pelo worker com a service_role.)

-- ── audit_log ─────────────────────────────────────────────────
alter table public.audit_log enable row level security;

drop policy if exists audit_admin_select on public.audit_log;
create policy audit_admin_select on public.audit_log
  for select using (public.is_admin());

-- (INSERT via RPC registrar_auditoria — ver 0003_rpc.sql.)
