-- ─────────────────────────────────────────────────────────────
-- 0011_auditoria_hardening.sql
-- Fecha o achado #6 da revisão: registrar_auditoria estava com EXECUTE
-- para PUBLIC (herdado por 'authenticated'), então qualquer usuário
-- logado podia chamá-la via RPC e forjar entradas na trilha de auditoria
-- atribuídas a si mesmo (p_action arbitrário).
--
-- Correção: a função passa a ser EXCLUSIVA do service_role e recebe o
-- usuário responsável por parâmetro (p_user_id) — pois o service_role
-- não tem auth.uid(). Todos os endpoints do servidor foram ajustados
-- para chamá-la com a service_role e o id do usuário que agiu.
-- ─────────────────────────────────────────────────────────────

-- Remove a versão antiga de 2 args (senão continua chamável por authenticated).
drop function if exists public.registrar_auditoria(text, jsonb);

create or replace function public.registrar_auditoria(
  p_action  text,
  p_detail  jsonb default '{}'::jsonb,
  p_user_id uuid  default null
)
returns void
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.audit_log (user_id, action, detail)
  values (
    coalesce(p_user_id, auth.uid()),
    p_action,
    coalesce(p_detail, '{}'::jsonb)
  );
end $$;

-- Só a service_role (server routes) chama. Bloqueia navegador/anon/authenticated.
revoke all on function public.registrar_auditoria(text, jsonb, uuid) from public;
revoke all on function public.registrar_auditoria(text, jsonb, uuid) from anon;
revoke all on function public.registrar_auditoria(text, jsonb, uuid) from authenticated;
grant execute on function public.registrar_auditoria(text, jsonb, uuid) to service_role;
