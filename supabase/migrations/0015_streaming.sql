-- ─────────────────────────────────────────────────────────────
-- 0015_streaming.sql · Novo sistema "Ativação de Streaming"
-- Relatório dos cadastros NOVOS do dia cujo plano inclui streaming
-- (Globoplay, Max/HBO, Telecine, Watch, Premiere, Disney+) — o que a equipe
-- precisa p/ ativar a TV. Roda no worker via API oficial do SGP (Token/App).
-- Param: 'data' (input type=date; vazio → hoje). Idempotente.
-- ─────────────────────────────────────────────────────────────
insert into public.systems (slug, name, description, allowed_roles, kind, param_schema, sort_order)
values
  (
    'streaming-ativacao',
    'Ativação de Streaming',
    'Cadastros novos do dia com streaming no plano (nome, e-mail, telefone, POP e plano) para a equipe ativar a TV.',
    '{admin,supervisor}',
    'job',
    jsonb_build_object(
      'data', jsonb_build_object(
        'type', 'date',
        'label', 'Data',
        'required', false,
        'default', ''
      )
    ),
    55
  )
on conflict (slug) do update set
  name          = excluded.name,
  description   = excluded.description,
  allowed_roles = excluded.allowed_roles,
  kind          = excluded.kind,
  param_schema  = excluded.param_schema,
  sort_order    = excluded.sort_order;
