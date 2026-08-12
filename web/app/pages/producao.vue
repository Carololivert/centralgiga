<script setup lang="ts">
import type { Job } from '~/types/db'
import type { CategoriaOS, ContagemPorCategoria, LinhaBarra, PontoColuna } from '~/types/producao'

// Painel de Produção — só admin/supervisor (o systems.allowed_roles controla o
// menu; este middleware garante o acesso à rota).
definePageMeta({ middleware: 'role', roles: ['admin', 'supervisor'] })

const client = useSupabaseClient()
const user = useSupabaseUser()
const toast = useToast()

const {
  de, ate, resumo, meses, carregando, erro,
  detalhe, detalheTruncado, carregandoDetalhe, categoriasDetalhe, limiteDetalhe,
  carregar, carregarDetalhe, definirPeriodo,
} = useProducao()

// ── Período ────────────────────────────────────────────────────────────
type Preset = 'hoje' | 'ontem' | 'semana' | 'mes' | 'mes-passado' | 'livre'

const preset = ref<Preset>('hoje')
/** mês escolhido no seletor de "mês fechado" ('' = nenhum) */
const mesEscolhido = ref('')

const PRESETS: { chave: Preset, rotulo: string }[] = [
  { chave: 'hoje', rotulo: 'Hoje' },
  { chave: 'ontem', rotulo: 'Ontem' },
  { chave: 'semana', rotulo: '7 dias' },
  { chave: 'mes', rotulo: 'Este mês' },
  { chave: 'mes-passado', rotulo: 'Mês passado' },
]

function aplicarPreset(p: Preset) {
  preset.value = p
  mesEscolhido.value = ''
  const hoje = hojeISO()
  if (p === 'hoje') definirPeriodo(hoje, hoje)
  else if (p === 'ontem') definirPeriodo(somarDias(hoje, -1), somarDias(hoje, -1))
  else if (p === 'semana') definirPeriodo(somarDias(hoje, -6), hoje)
  else if (p === 'mes') {
    const m = limitesDoMes(hoje)
    definirPeriodo(m.de, hoje) // até hoje: o resto do mês ainda não aconteceu
  }
  else if (p === 'mes-passado') {
    const m = limitesDoMes(hoje, -1)
    definirPeriodo(m.de, m.ate)
  }
  carregar()
}

/**
 * Datas digitadas à mão. Não usa `definirPeriodo` (que troca as pontas de
 * lugar): se alguém edita "De" para depois de "Até", inverter jogaria o valor
 * recém-digitado para o outro campo — a tela responderia mudando justamente o
 * campo em que a pessoa não mexeu. Aqui a data digitada MANDA e a outra ponta
 * acompanha.
 */
function mudarDe() {
  if (!de.value) return
  if (ate.value && de.value > ate.value) ate.value = de.value
  aplicarLivre()
}

function mudarAte() {
  if (!ate.value) return
  if (de.value && ate.value < de.value) de.value = ate.value
  aplicarLivre()
}

function aplicarLivre() {
  if (!de.value || !ate.value) return
  preset.value = 'livre'
  mesEscolhido.value = ''
  carregar()
}

// ── Relatório mensal: só os meses que já estão carregados no banco ─────
const itensMes = computed(() => [
  { label: 'Mês fechado…', value: '' },
  ...meses.value.map(m => ({
    label: `${nomeDoMes(m.mes)} · ${numero(m.total)} OS`,
    value: m.mes,
  })),
])

function aplicarMes(mes: string) {
  if (!mes) return
  preset.value = 'livre'
  const limites = limitesDoMes(mes)
  definirPeriodo(limites.de, limites.ate)
  carregar()
}

const umDiaSo = computed(() => de.value === ate.value)

const tituloPeriodo = computed(() => {
  if (!de.value || !ate.value) return ''
  if (umDiaSo.value) return `${diaLongo(de.value)} · ${diaDaSemana(de.value)}`
  return `${diaLongo(de.value)} a ${diaLongo(ate.value)}`
})

// ── Cabeçalho: quando o worker atualizou pela última vez ───────────────
const ultimaSync = computed(() => {
  const s = resumo.value?.ultima_sync
  if (!s) return null
  const quando = new Date(s.criado_em)
  return {
    ...s,
    texto: quando.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }),
    velha: Date.now() - quando.getTime() > 36 * 60 * 60 * 1000, // > 36h = rotina parada
  }
})

// ── KPIs ───────────────────────────────────────────────────────────────
const totais = computed(() => resumo.value?.totais)
const anterior = computed(() => resumo.value?.anterior)

const rotuloAnterior = computed(() => {
  const a = anterior.value
  if (!a) return ''
  return umDiaSo.value ? 'vs. dia anterior' : 'vs. período anterior'
})

const mediaPorDia = computed(() => {
  const t = totais.value
  if (!t || !t.dias_com_os) return 0
  return Math.round((t.total / t.dias_com_os) * 10) / 10
})

// ── Séries visíveis (a legenda liga/desliga) ───────────────────────────
const visiveis = ref<CategoriaOS[]>(CATEGORIAS.map(c => c.chave))
const seriesVisiveis = computed(() => CATEGORIAS.filter(c => visiveis.value.includes(c.chave)))

function alternarSerie(chave: CategoriaOS) {
  const atual = visiveis.value
  // nunca deixa apagar a última: um gráfico sem série nenhuma não diz nada
  if (atual.includes(chave) && atual.length === 1) return
  visiveis.value = atual.includes(chave) ? atual.filter(c => c !== chave) : [...atual, chave]
}

const totaisPorCategoria = computed(() => {
  const out: Partial<Record<CategoriaOS, number>> = {}
  for (const c of CATEGORIAS) out[c.chave] = totais.value?.[c.campo] ?? 0
  return out
})

/** Contagem do banco (por dia, por hora, total) → {categoria: valor} do gráfico. */
function valoresDe(fonte: ContagemPorCategoria | undefined) {
  const out: Record<string, number> = {}
  if (!fonte) return out
  for (const c of CATEGORIAS) out[c.chave] = fonte[c.campo] ?? 0
  return out
}

function somaVisivel(fonte: Record<string, number>) {
  return seriesVisiveis.value.reduce((s, c) => s + (fonte[c.chave] ?? 0), 0)
}

// ── Gráfico: fluxo por hora ────────────────────────────────────────────
const pontosHora = computed<PontoColuna[]>(() => {
  const horas = resumo.value?.por_hora ?? []
  if (!horas.length) return []
  const comDados = horas.filter(h => h.total > 0).map(h => h.hora)
  // sem nada no período: mostra o expediente (6h–21h) em vez de 24 colunas vazias
  const inicio = comDados.length ? Math.max(0, Math.min(...comDados) - 1) : 6
  const fim = comDados.length ? Math.min(23, Math.max(...comDados) + 1) : 21
  return horas
    .filter(h => h.hora >= inicio && h.hora <= fim)
    .map((h) => {
      const valores = valoresDe(h)
      return {
        chave: `h${h.hora}`,
        eixo: String(h.hora).padStart(2, '0'),
        titulo: `${hora2(h.hora)} às ${hora2(h.hora + 1 > 23 ? 0 : h.hora + 1)}`,
        sub: umDiaSo.value ? diaLongo(de.value) : 'somando o período',
        valores,
        total: somaVisivel(valores),
      }
    })
})

const picoHora = computed(() => {
  const p = [...pontosHora.value].sort((a, b) => b.total - a.total)[0]
  return p && p.total > 0 ? p : null
})

const aposAsDezoito = computed(() =>
  pontosHora.value.filter(p => Number(p.eixo) >= 18).reduce((s, p) => s + p.total, 0),
)

// ── Gráfico: dia a dia ─────────────────────────────────────────────────
const pontosDia = computed<PontoColuna[]>(() =>
  (resumo.value?.por_dia ?? []).map((d) => {
    const valores = valoresDe(d)
    return {
      chave: d.dia,
      eixo: d.dia.slice(8),
      titulo: diaLongo(d.dia),
      sub: diaDaSemana(d.dia),
      valores,
      total: somaVisivel(valores),
      atenuado: ehFimDeSemana(d.dia),
    }
  }),
)

// ── Barras: categorias ─────────────────────────────────────────────────
const linhasCategoria = computed<LinhaBarra[]>(() => {
  const t = totais.value
  if (!t) return []
  return CATEGORIAS
    .map(c => ({
      chave: c.chave,
      rotulo: c.rotulo,
      sub: t.total ? `${Math.round((t[c.campo] / t.total) * 100)}% do período` : '',
      valores: { [c.chave]: t[c.campo] },
      total: t[c.campo],
    }))
    .filter(l => l.total > 0)
    .sort((a, b) => b.total - a.total)
})

// ── Barras: POP ────────────────────────────────────────────────────────
const popTodas = ref(false)
const popCompleto = ref(false)
const LIMITE_POP = 12

const linhasPopTodas = computed<LinhaBarra[]>(() => {
  const chaves = seriesPop.value.map(s => s.chave)

  return (resumo.value?.por_pop ?? [])
    .map((p) => {
      const valores = valoresDe(p)
      const total = chaves.reduce((s, c) => s + (valores[c] ?? 0), 0)
      const partes = [
        p.instalacoes ? `${p.instalacoes} instalação${p.instalacoes > 1 ? 'ões' : ''}` : '',
        p.remocoes ? `${p.remocoes} remoção${p.remocoes > 1 ? 'ões' : ''}` : '',
      ].filter(Boolean)
      return {
        chave: p.pop,
        rotulo: p.pop,
        sub: popTodas.value ? `${p.total} OS no total` : partes.join(' · ') || 'nenhuma',
        valores,
        total,
      }
    })
    .filter(l => l.total > 0)
    .sort((a, b) => b.total - a.total)
})

const linhasPop = computed(() =>
  popCompleto.value ? linhasPopTodas.value : linhasPopTodas.value.slice(0, LIMITE_POP),
)

const seriesPop = computed(() =>
  popTodas.value ? CATEGORIAS : CATEGORIAS.filter(c => c.chave === 'instalacao' || c.chave === 'remocao'),
)

// ── Tabela: equipes ────────────────────────────────────────────────────
const equipes = computed(() => resumo.value?.por_equipe ?? [])

// ── Tabela: OS finalizadas ─────────────────────────────────────────────
const busca = ref('')
const mostrando = ref(60)

const detalheFiltrado = computed(() => {
  const termo = busca.value.trim().toLowerCase()
  if (!termo) return detalhe.value
  return detalhe.value.filter(o =>
    [o.cliente, o.pop, o.motivo, o.equipe, String(o.os_id), String(o.contrato ?? '')]
      .some(v => (v ?? '').toLowerCase().includes(termo)),
  )
})

const detalheVisivel = computed(() => detalheFiltrado.value.slice(0, mostrando.value))

watch([detalhe, busca], () => { mostrando.value = 60 })

function alternarCategoriaDetalhe(chave: CategoriaOS) {
  const atual = categoriasDetalhe.value
  // nunca deixa esvaziar: sem filtro nenhum a consulta traria TODAS as
  // categorias — o oposto do que "desmarquei tudo" quer dizer.
  if (atual.includes(chave) && atual.length === 1) return
  categoriasDetalhe.value = atual.includes(chave)
    ? atual.filter(c => c !== chave)
    : [...atual, chave]
  carregarDetalhe()
}

function exportar() {
  const nome = umDiaSo.value ? `producao-${de.value}.csv` : `producao-${de.value}_a_${ate.value}.csv`
  baixarTexto(nome, csvDasOS(detalheFiltrado.value))
  toast.add({ title: `${detalheFiltrado.value.length} linha(s) exportada(s)`, color: 'success' })
}

// ── Atualizar agora (enfileira a automação producao-sync) ──────────────
const sincronizando = ref(false)
let canalJob: any = null
let relogioSync: any = null

/** Se o worker estiver fora do ar, o job fica "na_fila" para sempre e nenhum
 *  evento chega. Sem este teto o botão giraria eternamente, sem explicar nada. */
const TIMEOUT_SYNC_MS = 3 * 60 * 1000

function encerrarSync() {
  sincronizando.value = false
  if (relogioSync) { clearTimeout(relogioSync); relogioSync = null }
  if (canalJob) { client.removeChannel(canalJob); canalJob = null }
}

async function atualizarAgora() {
  if (!user.value || sincronizando.value) return
  sincronizando.value = true

  const { data, error } = await client
    .from('jobs')
    .insert({
      system_slug: 'producao-sync',
      requested_by: user.value.id,
      params: { de: de.value, ate: ate.value },
      status: 'na_fila',
    } as never)
    .select()
    .single()

  if (error) {
    encerrarSync()
    toast.add({ title: 'Não foi possível atualizar', description: error.message, color: 'error' })
    return
  }

  toast.add({ title: 'Buscando no SGP…', description: 'A tela atualiza sozinha ao terminar.' })

  const job = data as Job
  if (canalJob) client.removeChannel(canalJob)
  canalJob = client
    .channel(`producao-sync-${job.id}`)
    .on('postgres_changes',
      { event: 'UPDATE', schema: 'public', table: 'jobs', filter: `id=eq.${job.id}` },
      async (payload: any) => {
        const atualizado = payload.new as Job
        if (atualizado.status === 'concluido') {
          encerrarSync()
          await carregar()
          toast.add({ title: 'Produção atualizada ✓', color: 'success' })
        }
        else if (atualizado.status === 'erro') {
          encerrarSync()
          toast.add({ title: 'A sincronização falhou', description: atualizado.error ?? '', color: 'error' })
        }
      })
    .subscribe()

  relogioSync = setTimeout(() => {
    encerrarSync()
    toast.add({
      title: 'A sincronização não respondeu',
      description: 'O pedido continua na fila. Confira se o worker está no ar e recarregue a página.',
      color: 'warning',
    })
  }, TIMEOUT_SYNC_MS)
}

const semDados = computed(() => !carregando.value && !!resumo.value && resumo.value.totais.total === 0)
const nuncaSincronizou = computed(() => !carregando.value && !!resumo.value && !resumo.value.ultima_sync)

onMounted(() => aplicarPreset('hoje'))
onUnmounted(encerrarSync)
</script>

<template>
  <UDashboardPanel id="producao">
    <template #header>
      <UDashboardNavbar title="Produção" icon="i-lucide-chart-column">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <span v-if="ultimaSync" class="hidden md:inline text-xs text-muted">
              atualizado {{ ultimaSync.texto }}
            </span>
            <UButton
              icon="i-lucide-refresh-cw"
              size="sm"
              color="neutral"
              variant="ghost"
              label="Atualizar agora"
              :loading="sincronizando"
              @click="atualizarAgora"
            />
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="space-y-6">
        <!-- Período -->
        <div class="flex flex-wrap items-end gap-3">
          <div class="flex flex-wrap gap-1.5">
            <UButton
              v-for="p in PRESETS"
              :key="p.chave"
              size="sm"
              :color="preset === p.chave ? 'primary' : 'neutral'"
              :variant="preset === p.chave ? 'solid' : 'outline'"
              :label="p.rotulo"
              @click="aplicarPreset(p.chave)"
            />
          </div>
          <USelect
            v-if="meses.length"
            v-model="mesEscolhido"
            :items="itensMes"
            size="sm"
            icon="i-lucide-calendar-check"
            class="min-w-52"
            @update:model-value="aplicarMes(String($event))"
          />

          <div class="flex items-end gap-2">
            <UFormField label="De" size="xs">
              <UInput v-model="de" type="date" size="sm" @change="mudarDe" />
            </UFormField>
            <UFormField label="Até" size="xs">
              <UInput v-model="ate" type="date" size="sm" @change="mudarAte" />
            </UFormField>
          </div>
          <p class="text-sm text-muted ml-auto">{{ tituloPeriodo }}</p>
        </div>

        <UAlert
          v-if="erro"
          color="error"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          title="Não consegui carregar a produção"
          :description="erro"
        />

        <UAlert
          v-else-if="resumo?.ultima_falha"
          color="error"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          title="A última sincronização falhou"
          :description="`Tentativa de ${diaLongo(resumo.ultima_falha.de)} a ${diaLongo(resumo.ultima_falha.ate)}: ${resumo.ultima_falha.erro ?? 'erro desconhecido'}. Os números abaixo são os da última atualização que deu certo.`"
        />

        <UAlert
          v-else-if="ultimaSync && ultimaSync.velha"
          color="warning"
          variant="subtle"
          icon="i-lucide-clock-alert"
          title="Os dados podem estar desatualizados"
          :description="`A última sincronização automática foi em ${ultimaSync.texto}. A rotina roda todo dia às 18h no worker — confira se ele está no ar.`"
        />

        <div v-if="carregando && !resumo" class="flex justify-center py-20 text-muted">
          <UIcon name="i-lucide-loader-circle" class="size-7 animate-spin" />
        </div>

        <!-- Nada no banco ainda -->
        <div v-else-if="nuncaSincronizou" class="text-center py-16">
          <UIcon name="i-lucide-database" class="size-9 mx-auto text-muted mb-3" />
          <p class="font-medium">Ainda não há produção carregada.</p>
          <p class="text-sm text-muted mt-1 max-w-lg mx-auto">
            A rotina do worker roda todo dia às 18h. Para ver os meses anteriores agora,
            abra <strong>Sincronizar Produção</strong> e escolha o período.
          </p>
          <div class="flex items-center justify-center gap-2 mt-4">
            <UButton icon="i-lucide-refresh-cw" label="Buscar este período" :loading="sincronizando" @click="atualizarAgora" />
            <UButton
              icon="i-lucide-calendar-range"
              color="neutral"
              variant="outline"
              label="Carregar meses anteriores"
              to="/sistema/producao-sync"
            />
          </div>
        </div>

        <template v-else-if="resumo && totais">
          <!-- KPIs · o número-herói é Instalações -->
          <div class="grid gap-4 grid-cols-2 lg:grid-cols-4">
            <ProducaoKpi
              rotulo="Instalações finalizadas"
              :valor="totais.instalacoes"
              :cor="corCategoria('instalacao')"
              :variacao="variacao(totais.instalacoes, anterior?.instalacoes ?? 0)"
              :variacao-rotulo="rotuloAnterior"
              sentido="positivo"
              destaque
            />
            <ProducaoKpi
              rotulo="Remoções finalizadas"
              :valor="totais.remocoes"
              :cor="corCategoria('remocao')"
              :variacao="variacao(totais.remocoes, anterior?.remocoes ?? 0)"
              :variacao-rotulo="rotuloAnterior"
            />
            <ProducaoKpi
              rotulo="Total de OS finalizadas"
              :valor="totais.total"
              icone="i-lucide-clipboard-check"
              :variacao="variacao(totais.total, anterior?.total ?? 0)"
              :variacao-rotulo="rotuloAnterior"
              :sub="`${totais.equipes} equipe(s) · ${totais.pops} POP(s)`"
            />
            <ProducaoKpi
              :rotulo="umDiaSo ? 'OS por equipe no dia' : 'Média por dia trabalhado'"
              :valor="umDiaSo ? Math.round((totais.total / Math.max(1, totais.equipes)) * 10) / 10 : mediaPorDia"
              icone="i-lucide-gauge"
              :sub="umDiaSo
                ? (totais.espera_media !== null ? `espera média de ${totais.espera_media} dia(s)` : '')
                : `${totais.dias_com_os} dia(s) com movimento`"
            />
          </div>

          <!-- Aviso de dia vazio -->
          <UAlert
            v-if="semDados"
            color="neutral"
            variant="subtle"
            icon="i-lucide-moon"
            title="Nenhuma OS finalizada neste período"
            :description="umDiaSo
              ? 'Se o dia ainda está correndo, lembre que a coleta automática só roda às 18h — use “Atualizar agora” para ver o parcial.'
              : 'Confira o período ou carregue os dados em Sincronizar Produção.'"
          />

          <template v-else>
            <!-- Fluxo por hora -->
            <UPageCard
              :title="umDiaSo ? 'Fluxo do dia' : 'Fluxo por hora'"
              :description="umDiaSo
                ? 'A que horas o campo entregou — cada coluna é uma hora do dia.'
                : 'Somando todos os dias do período: em que horário o campo fecha as ordens.'"
              icon="i-lucide-clock"
              variant="subtle"
            >
              <template #footer>
                <ProducaoLegenda
                  :series="CATEGORIAS"
                  :visiveis="visiveis"
                  :totais="totaisPorCategoria"
                  @alternar="alternarSerie"
                />
              </template>

              <ProducaoColunas
                :pontos="pontosHora"
                :series="seriesVisiveis"
                altura="h-56"
              />

              <div class="flex flex-wrap gap-x-6 gap-y-1 mt-4 text-sm text-muted">
                <span v-if="picoHora">
                  Pico às <strong class="text-default">{{ picoHora.eixo }}h</strong>
                  ({{ numero(picoHora.total) }} OS)
                </span>
                <span v-if="aposAsDezoito">
                  <strong class="text-default">{{ numero(aposAsDezoito) }}</strong>
                  finalizada(s) das 18h em diante
                </span>
                <!-- honestidade: sem esta linha a soma das colunas ficaria menor
                     que o total lá em cima e ninguém saberia por quê -->
                <span v-if="totais.sem_hora">
                  <strong class="text-default">{{ numero(totais.sem_hora) }}</strong>
                  sem hora registrada (fora deste gráfico)
                </span>
              </div>
            </UPageCard>

            <!-- Dia a dia -->
            <UPageCard
              v-if="!umDiaSo"
              title="Dia a dia"
              description="Como o período se comportou. Fins de semana aparecem mais fracos."
              icon="i-lucide-calendar-days"
              variant="subtle"
            >
              <template #footer>
                <ProducaoLegenda
                  :series="CATEGORIAS"
                  :visiveis="visiveis"
                  :totais="totaisPorCategoria"
                  @alternar="alternarSerie"
                />
              </template>
              <ProducaoColunas :pontos="pontosDia" :series="seriesVisiveis" altura="h-56" />
            </UPageCard>

            <!-- items-start: sem isso o grid estica os dois cards à mesma altura
                 e o conteúdo do mais curto fica boiando no rodapé -->
            <div class="grid gap-4 lg:grid-cols-2 items-start">
              <!-- Categorias -->
              <UPageCard
                title="O que foi feito"
                description="Todas as OS finalizadas, por tipo de serviço."
                icon="i-lucide-list"
                variant="subtle"
              >
                <ProducaoBarras
                  :linhas="linhasCategoria"
                  :series="CATEGORIAS"
                  largura-rotulo="w-36 sm:w-44"
                />
              </UPageCard>

              <!-- Equipes -->
              <UPageCard
                title="Por equipe"
                description="Quem fechou o quê no período."
                icon="i-lucide-users"
                variant="subtle"
              >
                <div class="overflow-x-auto">
                  <table class="w-full text-sm">
                    <thead class="text-xs text-muted border-b border-default">
                      <tr>
                        <th class="text-left font-medium pr-2 py-2">Equipe</th>
                        <th class="text-right font-medium px-2 py-2">Inst.</th>
                        <th class="text-right font-medium px-2 py-2">Rem.</th>
                        <th class="text-right font-medium px-2 py-2 hidden sm:table-cell">Mud.</th>
                        <th class="text-right font-medium px-2 py-2 hidden sm:table-cell">Corr.</th>
                        <th class="text-right font-medium px-2 py-2 hidden sm:table-cell">Romp.</th>
                        <th class="text-right font-medium pl-2 py-2">Total</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-default">
                      <tr v-for="e in equipes" :key="e.equipe" class="hover:bg-elevated/50">
                        <td class="pr-2 py-1.5 truncate max-w-[12rem]">{{ e.equipe }}</td>
                        <td class="px-2 py-1.5 text-right tabular-nums">{{ e.instalacoes || '—' }}</td>
                        <td class="px-2 py-1.5 text-right tabular-nums">{{ e.remocoes || '—' }}</td>
                        <td class="px-2 py-1.5 text-right tabular-nums hidden sm:table-cell">{{ e.mudancas || '—' }}</td>
                        <td class="px-2 py-1.5 text-right tabular-nums hidden sm:table-cell">{{ e.corretivas || '—' }}</td>
                        <td class="px-2 py-1.5 text-right tabular-nums hidden sm:table-cell">{{ e.rompimentos || '—' }}</td>
                        <td class="pl-2 py-1.5 text-right tabular-nums font-medium">{{ e.total }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </UPageCard>
            </div>

            <!-- POP -->
            <UPageCard
              title="Instalações e remoções por POP"
              :description="`${linhasPopTodas.length} POP(s) com movimento no período.`"
              icon="i-lucide-map-pin"
              variant="subtle"
            >
              <template #footer>
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <ProducaoLegenda :series="seriesPop" />
                  <div class="flex items-center gap-3">
                    <label class="flex items-center gap-2 text-xs text-muted cursor-pointer">
                      <USwitch v-model="popTodas" size="sm" />
                      todas as categorias
                    </label>
                    <UButton
                      v-if="linhasPopTodas.length > LIMITE_POP"
                      size="xs"
                      color="neutral"
                      variant="link"
                      :label="popCompleto ? 'ver só o top 12' : `ver todos os ${linhasPopTodas.length}`"
                      @click="popCompleto = !popCompleto"
                    />
                  </div>
                </div>
              </template>

              <ProducaoBarras v-if="linhasPop.length" :linhas="linhasPop" :series="seriesPop" />
              <p v-else class="text-sm text-muted">Nenhuma instalação ou remoção no período.</p>
            </UPageCard>

            <!-- Detalhe -->
            <UPageCard
              title="OS finalizadas"
              description="A lista que gerou os números acima."
              icon="i-lucide-table"
              variant="subtle"
            >
              <template #header>
                <div class="flex flex-wrap items-center gap-2">
                  <UButton
                    v-for="c in CATEGORIAS"
                    :key="c.chave"
                    size="xs"
                    :color="categoriasDetalhe.includes(c.chave) ? 'primary' : 'neutral'"
                    :variant="categoriasDetalhe.includes(c.chave) ? 'soft' : 'outline'"
                    @click="alternarCategoriaDetalhe(c.chave)"
                  >
                    <span class="size-2 rounded-full" :style="{ backgroundColor: c.cor }" />
                    {{ c.curto }}
                  </UButton>
                  <span class="ml-auto" />
                  <UInput
                    v-model="busca"
                    icon="i-lucide-search"
                    size="sm"
                    placeholder="cliente, POP, motivo, OS…"
                    class="w-52"
                  />
                  <UButton
                    icon="i-lucide-download"
                    size="sm"
                    color="neutral"
                    variant="outline"
                    label="CSV"
                    :disabled="!detalheFiltrado.length"
                    @click="exportar"
                  />
                </div>
              </template>

              <div v-if="carregandoDetalhe" class="flex justify-center py-10 text-muted">
                <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin" />
              </div>

              <div v-else-if="detalheVisivel.length" class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead class="text-xs text-muted border-b border-default">
                    <tr>
                      <th class="text-left font-medium pr-2 py-2">OS</th>
                      <th v-if="!umDiaSo" class="text-left font-medium px-2 py-2">Dia</th>
                      <th class="text-left font-medium px-2 py-2">Hora</th>
                      <th class="text-left font-medium px-2 py-2">Serviço</th>
                      <th class="text-left font-medium px-2 py-2">POP</th>
                      <th class="text-left font-medium px-2 py-2 hidden lg:table-cell">Equipe</th>
                      <th class="text-left font-medium pl-2 py-2 hidden md:table-cell">Cliente</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-default">
                    <tr v-for="o in detalheVisivel" :key="o.os_id" class="hover:bg-elevated/50">
                      <td class="pr-2 py-1.5 tabular-nums text-muted">{{ o.os_id }}</td>
                      <td v-if="!umDiaSo" class="px-2 py-1.5 tabular-nums whitespace-nowrap">
                        {{ diaCurto(o.data_finalizacao) }}
                      </td>
                      <td class="px-2 py-1.5 tabular-nums whitespace-nowrap">{{ horaCurta(o.hora_finalizacao) || '—' }}</td>
                      <td class="px-2 py-1.5">
                        <span class="inline-flex items-center gap-1.5">
                          <span class="size-2 rounded-full shrink-0" :style="{ backgroundColor: corCategoria(o.categoria) }" />
                          <span class="whitespace-nowrap">{{ rotuloCategoria(o.categoria) }}</span>
                          <span v-if="o.subcategoria" class="text-muted text-xs hidden xl:inline">
                            {{ rotuloSubcategoria(o.subcategoria) }}
                          </span>
                        </span>
                      </td>
                      <td class="px-2 py-1.5 max-w-[16rem] truncate" :title="o.pop ?? ''">{{ o.pop || '—' }}</td>
                      <td class="px-2 py-1.5 hidden lg:table-cell whitespace-nowrap">{{ o.equipe || '—' }}</td>
                      <td class="pl-2 py-1.5 hidden md:table-cell max-w-[18rem] truncate" :title="o.cliente ?? ''">
                        {{ o.cliente || '—' }}
                      </td>
                    </tr>
                  </tbody>
                </table>

                <div class="flex flex-wrap items-center gap-3 pt-3 text-xs text-muted">
                  <span>
                    Mostrando {{ numero(detalheVisivel.length) }} de {{ numero(detalheFiltrado.length) }}
                  </span>
                  <UButton
                    v-if="detalheVisivel.length < detalheFiltrado.length"
                    size="xs"
                    color="neutral"
                    variant="link"
                    label="carregar mais"
                    class="px-0"
                    @click="mostrando += 120"
                  />
                  <span v-if="detalheTruncado" class="text-warning">
                    ⚠️ O período passou de {{ numero(limiteDetalhe) }} OS — a lista foi cortada
                    (os gráficos acima continuam com o total certo). Use o CSV da automação para o detalhe completo.
                  </span>
                </div>
              </div>

              <p v-else class="text-sm text-muted">
                Nenhuma OS com os filtros escolhidos.
              </p>
            </UPageCard>
          </template>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>
