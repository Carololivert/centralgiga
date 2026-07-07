-- ─────────────────────────────────────────────────────────────
-- 0008_vendas_data.sql · Verificar Vendas: trocar o filtro fixo (hoje/todas)
-- por um SELETOR DE DATA na tela (input type=date) + switch "todas as datas".
-- O worker (adapter verificar_vendas) aceita a data ISO 'yyyy-mm-dd' do input,
-- a BR 'dd/mm/aaaa', 'hoje'/vazio (→ hoje) e 'todas'/switch (→ sem filtro).
-- Idempotente (roda quantas vezes quiser).
-- ─────────────────────────────────────────────────────────────
update public.systems
set param_schema = jsonb_build_object(
  'data', jsonb_build_object(
    'type', 'date',
    'label', 'Data',
    'required', false,
    'default', ''
  ),
  'todas', jsonb_build_object(
    'type', 'boolean',
    'label', 'Puxar todas as datas (ignora o campo Data)',
    'default', false
  )
)
where slug = 'verificar-vendas';
