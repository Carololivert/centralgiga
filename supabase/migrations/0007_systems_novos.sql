-- ─────────────────────────────────────────────────────────────
-- 0007_systems_novos.sql · Novos sistemas (Vendas, Linhas Canceladas, Remover Linhas)
-- Idempotente. Remover Linhas é AÇÃO (só admin) e roda em simulação por padrão.
-- ─────────────────────────────────────────────────────────────

insert into public.systems (slug, name, description, allowed_roles, kind, param_schema, sort_order)
values
  (
    'verificar-vendas',
    'Verificar Vendas',
    'Atendimentos de VENDAS (FocusChat) que ainda não viraram cliente no SGP.',
    '{admin,supervisor}',
    'job',
    jsonb_build_object(
      'data', jsonb_build_object(
        'type', 'select', 'label', 'Período', 'required', true, 'default', 'hoje',
        'options', to_jsonb(array['hoje', 'todas'])
      )
    ),
    50
  ),
  (
    'linhas-canceladas',
    'Linhas Canceladas',
    'Números de telefones de contratos cancelados no SGP — gera Excel com os números livres.',
    '{admin,supervisor}',
    'job',
    jsonb_build_object(
      'periodo', jsonb_build_object(
        'type', 'select', 'label', 'Período', 'required', true, 'default', 'Este mês',
        'options', to_jsonb(array['Este mês', 'Últimos 3 meses', 'Este ano'])
      )
    ),
    60
  ),
  (
    'remover-linhas',
    'Remover Linhas',
    'Remove no SGP as linhas de contratos cancelados. Rode a simulação antes de remover de verdade.',
    '{admin}',
    'job',
    jsonb_build_object(
      'dry_run', jsonb_build_object('type', 'boolean', 'label', 'Apenas simular (não remove)', 'default', true),
      'periodo', jsonb_build_object(
        'type', 'select', 'label', 'Período', 'required', true, 'default', 'Este mês',
        'options', to_jsonb(array['Este mês', 'Últimos 3 meses', 'Este ano'])
      )
    ),
    70
  )
on conflict (slug) do update set
  name          = excluded.name,
  description   = excluded.description,
  allowed_roles = excluded.allowed_roles,
  kind          = excluded.kind,
  param_schema  = excluded.param_schema,
  sort_order    = excluded.sort_order;
