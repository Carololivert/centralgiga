-- ─────────────────────────────────────────────────────────────
-- 0003_rpc.sql · Funções da fila e auditoria
-- ─────────────────────────────────────────────────────────────

-- ── claim_next_job: dequeue atômico para o worker ─────────────
-- FOR UPDATE SKIP LOCKED garante que dois workers não peguem o mesmo job.
create or replace function public.claim_next_job()
returns public.jobs
language plpgsql
security definer set search_path = public
as $$
declare
  j public.jobs;
begin
  select * into j
  from public.jobs
  where status = 'na_fila'
  order by created_at
  for update skip locked
  limit 1;

  if not found then
    return null;
  end if;

  update public.jobs
     set status = 'executando',
         started_at = now()
   where id = j.id
  returning * into j;

  return j;
end $$;

-- Só a service_role (worker) deve chamar. Revoga de anon/authenticated
-- e concede explicitamente à service_role (senão o worker perde o execute).
revoke all on function public.claim_next_job() from public;
revoke all on function public.claim_next_job() from anon;
revoke all on function public.claim_next_job() from authenticated;
grant execute on function public.claim_next_job() to service_role;

-- ── registrar_auditoria: log de ações (chamável pelo app logado) ─
create or replace function public.registrar_auditoria(
  p_action text,
  p_detail jsonb default '{}'::jsonb
)
returns void
language plpgsql
security definer set search_path = public
as $$
begin
  if public.auth_role() is null then
    raise exception 'sem permissão';
  end if;
  insert into public.audit_log (user_id, action, detail)
  values (auth.uid(), p_action, coalesce(p_detail, '{}'::jsonb));
end $$;
