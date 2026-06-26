-- ─────────────────────────────────────────────────────────────
-- 0005_storage.sql · Bucket privado de resultados + policies
-- O worker faz upload com a service_role (ignora RLS).
-- O frontend gera signed URL com a sessão do usuário (anon key),
-- liberado pela policy de leitura abaixo. Sem service_role no front.
-- ─────────────────────────────────────────────────────────────

insert into storage.buckets (id, name, public)
values ('resultados', 'resultados', false)
on conflict (id) do nothing;

-- Leitura: admin lê tudo; demais leem só objetos de jobs seus.
-- Convenção de path: resultados/{job_id}/arquivo  → foldername()[1] = job_id
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
