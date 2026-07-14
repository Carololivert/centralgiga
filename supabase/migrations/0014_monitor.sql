-- ─────────────────────────────────────────────────────────────
-- 0014_monitor.sql · Monitor de Rede (painel em tempo real)
--
-- Adiciona o tipo de sistema 'painel' (página própria, fora da fila de jobs) e
-- cadastra o "Monitor de Rede" — visível só para admin/supervisor. A tela é o
-- app Nuxt (/monitor); os dados vêm do serviço Python ../monitor/server.py via
-- as rotas server/api/monitor/* (que exigem o cargo). Não usa jobs/worker.
-- (Numerada 0014: vem depois da última migration existente, 0013.)
-- ─────────────────────────────────────────────────────────────

-- 1) Permitir o novo kind 'painel' no catálogo de sistemas.
--    (O CHECK original é definido inline em 0001_schema.sql como systems_kind_check.)
alter table public.systems drop constraint if exists systems_kind_check;
alter table public.systems
  add constraint systems_kind_check check (kind in ('job', 'inbox', 'painel'));

-- 2) Cadastrar o Monitor de Rede (idempotente).
insert into public.systems (slug, name, description, allowed_roles, kind, param_schema, sort_order)
values
  (
    'monitor',
    'Monitor de Rede',
    'Detector de rompimento de fibra em tempo real: temperatura das OLTs, PONs em LOS/parcial e quedas de energia — cruzando SmartOLT + SGP para mostrar os clientes afetados.',
    '{admin,supervisor}',
    'painel',
    '{}'::jsonb,
    5
  )
on conflict (slug) do update set
  name          = excluded.name,
  description   = excluded.description,
  allowed_roles = excluded.allowed_roles,
  kind          = excluded.kind,
  param_schema  = excluded.param_schema,
  sort_order    = excluded.sort_order;
