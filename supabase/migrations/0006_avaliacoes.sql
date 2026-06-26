-- ─────────────────────────────────────────────────────────────
-- 0006_avaliacoes.sql · Migração do módulo "Giganet Avaliações"
--   para a nova central.
--
-- ⚠️ CUTOVER — rode SÓ quando for migrar avaliações para cá:
--   • A central ANTIGA (Lista/) acessa giganet_reviews com a anon key
--     e RLS DESLIGADA. Esta migração LIGA o RLS, o que vai BLOQUEAR
--     o módulo giganet da central antiga.
--   • Reaponte o n8n: o webhook que hoje chama
--     POST {central-antiga}/api/giganet/webhook  deve passar a chamar
--     POST {central-nova}/api/avaliacoes/webhook  (mesmo x-webhook-secret).
-- ─────────────────────────────────────────────────────────────

-- ── Tabela trancada de segredos (RLS on, sem policy = ninguém lê) ─
-- Só funções security definer (donas = postgres) conseguem ler.
create table if not exists public.app_secrets (
  key   text primary key,
  value text not null
);
alter table public.app_secrets enable row level security;

-- Segredo do header x-webhook-secret. TROQUE pelo valor real (= GIGANET_WEBHOOK_SECRET
-- do .env). 'do nothing' evita sobrescrever o valor real já configurado no banco.
insert into public.app_secrets (key, value)
values ('giganet_webhook_secret', 'TROQUE-PELO-SEGREDO-REAL')
on conflict (key) do nothing;

-- ── RLS no giganet_reviews (substitui o modelo antigo sem RLS) ─
alter table public.giganet_reviews enable row level security;

drop policy if exists reviews_admin_read on public.giganet_reviews;
create policy reviews_admin_read on public.giganet_reviews
  for select using (public.is_admin());

drop policy if exists reviews_admin_update on public.giganet_reviews;
create policy reviews_admin_update on public.giganet_reviews
  for update using (public.is_admin()) with check (public.is_admin());

drop policy if exists reviews_admin_delete on public.giganet_reviews;
create policy reviews_admin_delete on public.giganet_reviews
  for delete using (public.is_admin());

-- (INSERT só via RPC abaixo — o n8n não tem sessão de usuário.)

-- ── RPC de inserção via webhook (protegida por segredo) ───────
create or replace function public.webhook_inserir_avaliacao(
  p_secret        text,
  p_review_id     text,
  p_reviewer_name text,
  p_star_rating   int,
  p_comment       text,
  p_ai_response   text,
  p_resume_url    text
)
returns public.giganet_reviews
language plpgsql
security definer set search_path = public
as $$
declare
  r public.giganet_reviews;
begin
  if p_secret is distinct from (select value from public.app_secrets where key = 'giganet_webhook_secret') then
    raise exception 'segredo inválido';
  end if;

  if coalesce(p_ai_response, '') = '' then
    raise exception 'ai_response obrigatório';
  end if;

  insert into public.giganet_reviews
    (review_id, reviewer_name, star_rating, comment, ai_response, resume_url, status)
  values (
    nullif(p_review_id, ''),
    nullif(p_reviewer_name, ''),
    case when p_star_rating between 1 and 5 then p_star_rating else null end,
    nullif(p_comment, ''),
    p_ai_response,
    nullif(p_resume_url, ''),
    'pending'
  )
  returning * into r;

  return r;
end $$;
