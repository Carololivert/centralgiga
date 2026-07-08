-- ─────────────────────────────────────────────────────────────
-- 0012_seguranca_rls_admin.sql
-- Corrige uma lacuna do 0010: session_plena() (2FA concluído + senha
-- trocada) foi aplicado só nas policies "de leitura por cargo". As
-- policies de ADMIN (que gatilham só is_admin()) ficaram de fora — então
-- uma sessão AAL1 de admin (senha sem 2FA, ou senha provisória) ainda
-- alcançava profiles/systems/jobs(delete)/giganet_reviews/storage direto
-- pelo PostgREST, inclusive PODENDO SE AUTO-PROMOVER editando profiles.
-- Aqui fechamos todas com o mesmo gate.
--
-- Também: usuários novos passam a nascer INATIVOS (fail-closed). Só o
-- fluxo de admin (server/api/usuarios/index.post.ts) os ativa. Assim, um
-- cadastro público (se estiver habilitado no projeto) não vira "sessão
-- plena" sozinho — e must_change_password NÃO serve de trava porque o
-- próprio usuário a limpa em /conta/definir-senha; 'active' ninguém limpa.
-- ─────────────────────────────────────────────────────────────

-- ── profiles ──────────────────────────────────────────────────
-- Escrita/gestão de TODOS os perfis exige sessão plena.
drop policy if exists profiles_admin_all on public.profiles;
create policy profiles_admin_all on public.profiles
  for all
  using (public.session_plena() and public.is_admin())
  with check (public.session_plena() and public.is_admin());

-- Leitura: o PRÓPRIO perfil sempre (onboarding em AAL1); ler os demais
-- (admin) exige sessão plena — senão um admin AAL1 lista todos os perfis (PII).
drop policy if exists profiles_self_select on public.profiles;
create policy profiles_self_select on public.profiles
  for select using (
    id = auth.uid()
    or (public.session_plena() and public.is_admin())
  );

-- ── systems ───────────────────────────────────────────────────
-- FOR ALL cobre SELECT e faz OR com systems_select; sem o gate aqui, o
-- session_plena do systems_select fica sem efeito para admin. Fechamos.
drop policy if exists systems_admin_write on public.systems;
create policy systems_admin_write on public.systems
  for all
  using (public.session_plena() and public.is_admin())
  with check (public.session_plena() and public.is_admin());

-- ── jobs ──────────────────────────────────────────────────────
drop policy if exists jobs_admin_delete on public.jobs;
create policy jobs_admin_delete on public.jobs
  for delete using (public.session_plena() and public.is_admin());

-- ── giganet_reviews (PII de clientes) ─────────────────────────
drop policy if exists reviews_admin_read on public.giganet_reviews;
create policy reviews_admin_read on public.giganet_reviews
  for select using (public.session_plena() and public.is_admin());

drop policy if exists reviews_admin_update on public.giganet_reviews;
create policy reviews_admin_update on public.giganet_reviews
  for update using (public.session_plena() and public.is_admin())
  with check (public.session_plena() and public.is_admin());

drop policy if exists reviews_admin_delete on public.giganet_reviews;
create policy reviews_admin_delete on public.giganet_reviews
  for delete using (public.session_plena() and public.is_admin());
-- (INSERT continua só via RPC webhook_inserir_avaliacao — security definer.)

-- ── storage: bucket 'resultados' ──────────────────────────────
-- session_plena no topo cobre os dois ramos (admin e dono do job).
drop policy if exists resultados_read on storage.objects;
create policy resultados_read on storage.objects
  for select to authenticated
  using (
    bucket_id = 'resultados'
    and public.session_plena()
    and (
      public.is_admin()
      or (storage.foldername(name))[1] in (
        select id::text from public.jobs where requested_by = auth.uid()
      )
    )
  );

-- ── Fail-closed no cadastro: usuário novo nasce INATIVO ───────
-- O fluxo de admin (index.post.ts) faz update active=true logo após criar.
-- auth_role() e session_plena() já exigem active=true, então um cadastro
-- fora do fluxo de admin fica inerte até um admin ativar.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, full_name, role, active)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', split_part(new.email, '@', 1)),
    'atendente',  -- nunca confiar em role do metadata
    false         -- fail-closed: só o admin ativa
  )
  on conflict (id) do nothing;
  return new;
end $$;
