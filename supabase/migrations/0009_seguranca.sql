-- ─────────────────────────────────────────────────────────────
-- 0009_seguranca.sql · Segurança de login
--   • must_change_password: usuário recebe senha provisória e é
--     obrigado a definir uma senha própria no 1º acesso.
--   • password_changed_at: auditoria de quando trocou.
-- (O 2FA/TOTP é gerido nativamente pelo Supabase Auth — não precisa
--  de tabela; os fatores ficam em auth.mfa_factors.)
-- ─────────────────────────────────────────────────────────────

alter table public.profiles
  add column if not exists must_change_password boolean not null default false;

alter table public.profiles
  add column if not exists password_changed_at timestamptz;

comment on column public.profiles.must_change_password is
  'true = senha atual é provisória; o usuário deve definir uma senha própria no próximo acesso.';

-- Usuários já existentes continuam com must_change_password = false
-- (não queremos travar quem já usa o sistema). Apenas usuários NOVOS,
-- criados pela tela de administração, recebem senha provisória.

-- ── Quem já tem 2FA verificado (para exibir status na tela de admin) ──
-- Lê auth.mfa_factors, fora do alcance do PostgREST; por isso via função
-- security definer. Só a service_role (server route de admin) pode chamar.
create or replace function public.usuarios_com_2fa()
returns setof uuid
language sql
stable
security definer
set search_path = public, auth
as $$
  select distinct user_id
  from auth.mfa_factors
  where status = 'verified'
$$;

revoke all on function public.usuarios_com_2fa() from public;
revoke all on function public.usuarios_com_2fa() from anon;
revoke all on function public.usuarios_com_2fa() from authenticated;
grant execute on function public.usuarios_com_2fa() to service_role;
