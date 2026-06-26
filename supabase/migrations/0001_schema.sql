-- ─────────────────────────────────────────────────────────────
-- 0001_schema.sql · Central de Automações Giganet
-- Tabelas: profiles, systems, jobs, job_logs, audit_log
-- (giganet_reviews JÁ existe neste projeto; ver 0006_avaliacoes.sql)
-- Rode na ordem 0001 → 0006 no SQL Editor do Supabase (ou via CLI).
-- ─────────────────────────────────────────────────────────────

create extension if not exists "pgcrypto";

-- ── Tipos ─────────────────────────────────────────────────────
do $$ begin
  create type public.user_role as enum ('admin', 'supervisor', 'atendente');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.job_status as enum ('na_fila', 'executando', 'concluido', 'erro');
exception when duplicate_object then null; end $$;

-- ── profiles (1:1 com auth.users) ─────────────────────────────
create table if not exists public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  full_name   text,
  role        public.user_role not null default 'atendente',
  active      boolean not null default true,
  created_at  timestamptz not null default now()
);

-- ── systems (catálogo de automações + permissão por cargo) ────
create table if not exists public.systems (
  id            uuid primary key default gen_random_uuid(),
  slug          text unique not null,
  name          text not null,
  description   text,
  allowed_roles public.user_role[] not null default '{}',
  -- 'job'   = vai pra fila e o worker executa
  -- 'inbox' = módulo próprio (ex. avaliações), fora da fila
  kind          text not null default 'job' check (kind in ('job', 'inbox')),
  -- descreve os parâmetros do formulário (renderizado no frontend)
  param_schema  jsonb not null default '{}'::jsonb,
  sort_order    int not null default 100,
  active        boolean not null default true,
  created_at    timestamptz not null default now()
);

-- ── jobs (fila de execução) ───────────────────────────────────
create table if not exists public.jobs (
  id             uuid primary key default gen_random_uuid(),
  system_slug    text not null references public.systems(slug),
  requested_by   uuid not null references auth.users(id),
  status         public.job_status not null default 'na_fila',
  params         jsonb not null default '{}'::jsonb,
  error          text,
  result_path    text,    -- caminho no Storage (bucket privado 'resultados')
  result_preview text,    -- prévia textual do resultado (para exibir inline)
  created_at     timestamptz not null default now(),
  started_at     timestamptz,
  finished_at    timestamptz
);
create index if not exists jobs_status_idx       on public.jobs (status, created_at);
create index if not exists jobs_requested_by_idx on public.jobs (requested_by, created_at desc);
create index if not exists jobs_system_idx       on public.jobs (system_slug, created_at desc);

-- ── job_logs (log ao vivo) ────────────────────────────────────
create table if not exists public.job_logs (
  id          bigint generated always as identity primary key,
  job_id      uuid not null references public.jobs(id) on delete cascade,
  level       text not null default 'info' check (level in ('info', 'warn', 'error', 'debug')),
  line        text not null,
  created_at  timestamptz not null default now()
);
create index if not exists job_logs_job_idx on public.job_logs (job_id, id);

-- ── audit_log (ações de admin) ────────────────────────────────
create table if not exists public.audit_log (
  id          bigint generated always as identity primary key,
  user_id     uuid references auth.users(id),
  action      text not null,
  detail      jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index if not exists audit_log_created_idx on public.audit_log (created_at desc);

-- ── Trigger: cria o profile automaticamente ao criar um auth.user
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
    coalesce((new.raw_user_meta_data ->> 'role')::public.user_role, 'atendente')
  )
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ── Realtime: publica jobs e job_logs (status + log ao vivo) ──
do $$ begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'jobs'
  ) then
    alter publication supabase_realtime add table public.jobs;
  end if;
end $$;

do $$ begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'job_logs'
  ) then
    alter publication supabase_realtime add table public.job_logs;
  end if;
end $$;
