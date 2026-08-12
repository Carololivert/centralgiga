-- ─────────────────────────────────────────────────────────────
-- 0016_producao.sql · Dashboard de Produção (OS finalizadas)
--
-- Guarda no banco TODA ordem de serviço FINALIZADA no SGP (instalação,
-- remoção, mudança, corretiva, rompimento…) com POP, equipe e hora — para o
-- painel /producao mostrar o fluxo do dia e o fechamento do mês.
--
-- Fonte: SGP `/api/ura/ordemservico/list/` filtrando por data_finalizacao
-- (só devolve OS "Encerrada"). Quem grava é o worker, com a service_role:
--   • todo dia às 18h (worker/agenda.py — horário em que o técnico encerra);
--   • sob demanda pela automação 'producao-sync' (backfill/reprocessar).
--
-- Idempotente: os_id é a PK, então re-sincronizar o mesmo dia só ATUALIZA
-- (é assim que finalização lançada tarde da noite entra no dia seguinte).
-- ─────────────────────────────────────────────────────────────

-- ── Fato: uma linha por OS finalizada ─────────────────────────
create table if not exists public.os_producao (
  os_id               bigint      primary key,          -- id da OS no SGP
  ocorrencia          text,
  cliente             text,
  contrato            integer,
  contrato_status     text,
  tipo                text,                             -- Externa / Interna
  status              text,                             -- sempre "Encerrada" aqui
  motivo              text        not null default '',
  -- categoria: instalacao | remocao | mudanca | corretiva | rompimento |
  --            servico | outros   (derivada do motivo pelo worker)
  categoria           text        not null default 'outros',
  subcategoria        text,                             -- casa | condominio | predio | …
  pop                 text,                             -- "Fibra 5 - Itapõa"
  pop_num             integer,                          -- 5 (para ordenar/agrupar)
  pop_regiao          text,                             -- "Itapõa"
  equipe              text,                             -- responsavel: "EQUIPE F"
  usuario_abertura    text,
  usuario_finalizacao text,
  tecnicos            text[]      not null default '{}',
  data_cadastro       date,
  data_agendamento    date,
  data_finalizacao    date        not null,
  hora_finalizacao    time,
  -- data + hora de finalização já no fuso de Brasília (para ordenar no detalhe)
  finalizado_em       timestamptz,
  -- dias entre a abertura e a finalização (fila do técnico)
  espera_dias         integer,
  atualizado_em       timestamptz not null default now()
);

create index if not exists os_producao_dia_idx       on public.os_producao (data_finalizacao desc);
create index if not exists os_producao_categoria_idx on public.os_producao (categoria, data_finalizacao desc);
create index if not exists os_producao_pop_idx       on public.os_producao (pop, data_finalizacao desc);
create index if not exists os_producao_equipe_idx    on public.os_producao (equipe, data_finalizacao desc);

-- ── Log de sincronizações (o painel mostra "atualizado às …") ──
create table if not exists public.os_sync (
  id          bigint generated always as identity primary key,
  origem      text        not null default 'agenda'
                          check (origem in ('agenda', 'manual', 'backfill')),
  de          date        not null,
  ate         date        not null,
  total       integer     not null default 0,   -- OS lidas no SGP
  gravados    integer     not null default 0,   -- linhas enviadas ao upsert
  duracao_ms  integer,
  ok          boolean     not null default true,
  erro        text,
  criado_em   timestamptz not null default now()
);
create index if not exists os_sync_criado_idx on public.os_sync (criado_em desc);

-- ── RLS: leitura para admin/supervisor; escrita só service_role ──
-- (o worker usa a service_role, que ignora RLS — por isso não há policy de
--  INSERT/UPDATE: ninguém logado no app consegue escrever nessas tabelas.)
alter table public.os_producao enable row level security;
alter table public.os_sync     enable row level security;

drop policy if exists os_producao_select on public.os_producao;
create policy os_producao_select on public.os_producao
  for select using (
    public.is_admin() or public.auth_role() = 'supervisor'
  );

drop policy if exists os_sync_select on public.os_sync;
create policy os_sync_select on public.os_sync
  for select using (
    public.is_admin() or public.auth_role() = 'supervisor'
  );

-- ── RPC do painel: um JSON com tudo que a tela desenha ────────
-- security INVOKER (padrão) de propósito: a RLS acima continua valendo, então
-- a função só devolve dados para admin/supervisor.
create or replace function public.producao_resumo(p_de date, p_ate date)
returns jsonb
language sql
stable
set search_path = public
as $$
with
  periodo as (
    -- O teto de 366 dias não é capricho: `dias` abaixo faz generate_series só
    -- com os PARÂMETROS (não lê a tabela), então a RLS não segura o custo — sem
    -- o limite, um p_de=1000-01-01 faria o Postgres montar milhões de linhas e
    -- um jsonb gigante. O painel nunca pede mais que um mês.
    select least(p_de, p_ate) as de,
           least(greatest(p_de, p_ate), least(p_de, p_ate) + 366) as ate
  ),
  -- Janela de comparação ("vs período anterior"). Mês civil inteiro compara com
  -- o MÊS ANTERIOR inteiro; qualquer outro período compara com a janela de
  -- mesmo tamanho logo antes. (Sem esse caso, julho — 31 dias — cairia em
  -- 31/05 a 30/06, misturando dois meses e sujando o fechamento mensal.)
  anterior as (
    select
      case when mes_cheio then (de - interval '1 month')::date
           else (de - (ate - de + 1))::date end as de,
      case when mes_cheio then (de - interval '1 day')::date
           else (de - 1)::date end as ate
    from (
      select de, ate,
             de = date_trunc('month', de)::date
             and ate = (date_trunc('month', de) + interval '1 month' - interval '1 day')::date
               as mes_cheio
      from periodo
    ) t
  ),
  base as (
    select o.* from public.os_producao o, periodo p
    where o.data_finalizacao between p.de and p.ate
  ),
  base_ant as (
    select o.* from public.os_producao o, anterior a
    where o.data_finalizacao between a.de and a.ate
  ),
  -- todos os dias do período, inclusive os sem OS (senão o gráfico "pula" dias)
  dias as (
    select g.dia::date as dia
    from periodo p, generate_series(p.de, p.ate, interval '1 day') as g(dia)
  ),
  horas as (select g.hora from generate_series(0, 23) as g(hora))
select jsonb_build_object(
  'periodo', (
    select jsonb_build_object('de', p.de, 'ate', p.ate, 'dias', (p.ate - p.de + 1))
    from periodo p
  ),
  'totais', (
    select jsonb_build_object(
      'total',       count(*),
      'instalacoes', count(*) filter (where categoria = 'instalacao'),
      'remocoes',    count(*) filter (where categoria = 'remocao'),
      'mudancas',    count(*) filter (where categoria = 'mudanca'),
      'corretivas',  count(*) filter (where categoria = 'corretiva'),
      'rompimentos', count(*) filter (where categoria = 'rompimento'),
      'servicos',    count(*) filter (where categoria = 'servico'),
      'outros',      count(*) filter (where categoria = 'outros'),
      'equipes',     count(distinct equipe) filter (where coalesce(equipe, '') <> ''),
      'pops',        count(distinct pop)    filter (where coalesce(pop, '') <> ''),
      -- dias ÚTEIS (com pelo menos uma OS) — média por dia parado não engana
      'dias_com_os', count(distinct data_finalizacao),
      'espera_media', round(avg(espera_dias)::numeric, 1),
      -- OS sem hora de finalização não entram em `por_hora` (não há balde para
      -- elas). Expomos a contagem para a tela poder avisar em vez de deixar a
      -- soma das colunas silenciosamente menor que este total.
      'sem_hora', count(*) filter (where hora_finalizacao is null)
    ) from base
  ),
  'anterior', (
    select jsonb_build_object(
      'total',       count(*),
      'instalacoes', count(*) filter (where categoria = 'instalacao'),
      'remocoes',    count(*) filter (where categoria = 'remocao'),
      'de',          (select de  from anterior),
      'ate',         (select ate from anterior)
    ) from base_ant
  ),
  'por_dia', (
    select coalesce(jsonb_agg(x order by x->>'dia'), '[]'::jsonb) from (
      select jsonb_build_object(
        'dia',         d.dia,
        'total',       count(b.os_id),
        'instalacoes', count(b.os_id) filter (where b.categoria = 'instalacao'),
        'remocoes',    count(b.os_id) filter (where b.categoria = 'remocao'),
        'mudancas',    count(b.os_id) filter (where b.categoria = 'mudanca'),
        'corretivas',  count(b.os_id) filter (where b.categoria = 'corretiva'),
        'rompimentos', count(b.os_id) filter (where b.categoria = 'rompimento'),
        'servicos',    count(b.os_id) filter (where b.categoria = 'servico'),
        'outros',      count(b.os_id) filter (where b.categoria = 'outros')
      ) as x
      from dias d left join base b on b.data_finalizacao = d.dia
      group by d.dia
    ) t
  ),
  'por_hora', (
    select coalesce(jsonb_agg(x order by (x->>'hora')::int), '[]'::jsonb) from (
      select jsonb_build_object(
        'hora',        h.hora,
        'total',       count(b.os_id),
        'instalacoes', count(b.os_id) filter (where b.categoria = 'instalacao'),
        'remocoes',    count(b.os_id) filter (where b.categoria = 'remocao'),
        'mudancas',    count(b.os_id) filter (where b.categoria = 'mudanca'),
        'corretivas',  count(b.os_id) filter (where b.categoria = 'corretiva'),
        'rompimentos', count(b.os_id) filter (where b.categoria = 'rompimento'),
        'servicos',    count(b.os_id) filter (where b.categoria = 'servico'),
        'outros',      count(b.os_id) filter (where b.categoria = 'outros')
      ) as x
      from horas h
      left join base b on extract(hour from b.hora_finalizacao)::int = h.hora
      group by h.hora
    ) t
  ),
  'por_categoria', (
    select coalesce(jsonb_agg(x order by (x->>'total')::int desc), '[]'::jsonb) from (
      select jsonb_build_object('categoria', categoria, 'total', count(*)) as x
      from base group by categoria
    ) t
  ),
  'por_pop', (
    select coalesce(jsonb_agg(x order by (x->>'total')::int desc), '[]'::jsonb) from (
      select jsonb_build_object(
        'pop',         coalesce(nullif(pop, ''), '(sem POP)'),
        'pop_num',     max(pop_num),
        'total',       count(*),
        'instalacoes', count(*) filter (where categoria = 'instalacao'),
        'remocoes',    count(*) filter (where categoria = 'remocao'),
        'mudancas',    count(*) filter (where categoria = 'mudanca'),
        'corretivas',  count(*) filter (where categoria = 'corretiva'),
        'rompimentos', count(*) filter (where categoria = 'rompimento'),
        'servicos',    count(*) filter (where categoria = 'servico'),
        'outros',      count(*) filter (where categoria = 'outros')
      ) as x
      from base group by coalesce(nullif(pop, ''), '(sem POP)')
    ) t
  ),
  'por_equipe', (
    select coalesce(jsonb_agg(x order by (x->>'total')::int desc), '[]'::jsonb) from (
      select jsonb_build_object(
        'equipe',      coalesce(nullif(equipe, ''), '(sem equipe)'),
        'total',       count(*),
        'instalacoes', count(*) filter (where categoria = 'instalacao'),
        'remocoes',    count(*) filter (where categoria = 'remocao'),
        'mudancas',    count(*) filter (where categoria = 'mudanca'),
        'corretivas',  count(*) filter (where categoria = 'corretiva'),
        'rompimentos', count(*) filter (where categoria = 'rompimento')
      ) as x
      from base group by coalesce(nullif(equipe, ''), '(sem equipe)')
    ) t
  ),
  'por_motivo', (
    select coalesce(jsonb_agg(x order by (x->>'total')::int desc), '[]'::jsonb) from (
      select jsonb_build_object(
        'motivo',    coalesce(nullif(motivo, ''), '(sem motivo)'),
        'categoria', min(categoria),
        'total',     count(*)
      ) as x
      from base group by coalesce(nullif(motivo, ''), '(sem motivo)')
    ) t
  ),
  -- Última passada que deu CERTO. Filtrar por ok é o que faz o "atualizado às"
  -- dizer a verdade: sem isso, uma tentativa que falhou às 18h renovaria a data
  -- e desarmaria justamente o alerta de "a rotina parou".
  'ultima_sync', (
    select to_jsonb(s) from (
      select criado_em, origem, de, ate, total, gravados, ok, erro
      from public.os_sync where ok order by criado_em desc limit 1
    ) s
  ),
  -- Falha ainda NÃO superada (mais recente que a última passada boa) — a tela
  -- mostra o erro em vez de fingir que está tudo certo.
  'ultima_falha', (
    select to_jsonb(s) from (
      select criado_em, origem, de, ate, erro
      from public.os_sync
      where not ok
        and criado_em > coalesce(
          (select max(criado_em) from public.os_sync where ok), '-infinity'::timestamptz)
      order by criado_em desc limit 1
    ) s
  )
);
$$;

-- ⚠️ `from public` sozinho NÃO basta: o bootstrap do Supabase dá EXECUTE
-- explícito a anon/authenticated por default privileges, e revogar de PUBLIC
-- não desfaz um grant explícito. Mesmo padrão de 0003_rpc.sql.
revoke all on function public.producao_resumo(date, date) from public, anon;
grant execute on function public.producao_resumo(date, date) to authenticated;

-- ── Meses já disponíveis (alimenta o seletor de mês da tela) ──
create or replace function public.producao_meses()
returns table (mes date, total bigint)
language sql
stable
set search_path = public
as $$
  select date_trunc('month', data_finalizacao)::date as mes, count(*) as total
  from public.os_producao
  group by 1
  order by 1 desc
$$;

revoke all on function public.producao_meses() from public, anon;
grant execute on function public.producao_meses() to authenticated;

-- ── Catálogo: o painel + a automação de sincronização ─────────
insert into public.systems (slug, name, description, allowed_roles, kind, param_schema, sort_order)
values
  (
    'producao',
    'Produção',
    'Dashboard das OS finalizadas: instalações e remoções por POP, fluxo do dia hora a hora e fechamento mensal. Atualiza sozinho todo dia às 18h.',
    '{admin,supervisor}',
    'painel',
    '{}'::jsonb,
    6
  ),
  (
    'producao-sync',
    'Sincronizar Produção',
    'Puxa do SGP as OS finalizadas de um período e alimenta o dashboard de Produção. Use para carregar meses anteriores ou reprocessar um dia.',
    '{admin,supervisor}',
    'job',
    jsonb_build_object(
      'de', jsonb_build_object(
        'type', 'date', 'label', 'De (data de finalização)', 'required', false, 'default', ''
      ),
      'ate', jsonb_build_object(
        'type', 'date', 'label', 'Até', 'required', false, 'default', ''
      )
    ),
    95
  )
on conflict (slug) do update set
  name          = excluded.name,
  description   = excluded.description,
  allowed_roles = excluded.allowed_roles,
  kind          = excluded.kind,
  param_schema  = excluded.param_schema,
  sort_order    = excluded.sort_order;
