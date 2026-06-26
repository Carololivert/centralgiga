-- ─────────────────────────────────────────────────────────────
-- 0004_seed.sql · Catálogo dos sistemas (idempotente)
-- ─────────────────────────────────────────────────────────────

insert into public.systems (slug, name, description, allowed_roles, kind, param_schema, sort_order)
values
  (
    'relatorio-os',
    'Relatório de OS',
    'Resumo por equipe (A–I) das OS finalizadas do dia: corretivas, instalações, mudanças e fibras atendidas.',
    '{admin,supervisor}',
    'job',
    '{}'::jsonb,
    10
  ),
  (
    'termos-agendados',
    'Termos Agendados',
    'Instalações agendadas para amanhã que estão sem o termo (manual/eletrônico) preenchido na OS.',
    '{admin,supervisor}',
    'job',
    '{}'::jsonb,
    20
  ),
  (
    'conferencia-checklist',
    'Conferência de Checklist',
    'Avaliação automática (com IA) dos checklists das OS de uma equipe.',
    '{admin,atendente}',
    'job',
    jsonb_build_object(
      'equipe', jsonb_build_object(
        'type', 'select',
        'label', 'Equipe',
        'required', true,
        'default', 'EQUIPE F',
        'options', to_jsonb(array[
          'EQUIPE A','EQUIPE B','EQUIPE C','EQUIPE D','EQUIPE E',
          'EQUIPE F','EQUIPE G','EQUIPE H','EQUIPE I'
        ])
      )
    ),
    30
  ),
  (
    'giganet-avaliacoes',
    'Giganet Avaliações',
    'Aprovar, editar ou rejeitar as respostas geradas por IA às avaliações do Google.',
    '{admin}',
    'inbox',
    '{}'::jsonb,
    40
  )
on conflict (slug) do update set
  name          = excluded.name,
  description   = excluded.description,
  allowed_roles = excluded.allowed_roles,
  kind          = excluded.kind,
  param_schema  = excluded.param_schema,
  sort_order    = excluded.sort_order;
