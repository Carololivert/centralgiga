<script setup lang="ts">
import type { PontoColuna } from '~/types/producao'
import type { DefCategoria } from '~/utils/producao'

/**
 * Colunas empilhadas — o gráfico de "fluxo": OS finalizadas por hora do dia ou
 * por dia do mês, quebradas por categoria.
 *
 * Só HTML/CSS (nada de SVG nem biblioteca): o texto fica nítido em qualquer
 * zoom, o tema claro/escuro sai de graça pelos tokens e a área de hover pode
 * ser maior que a barra — que é o que faz uma coluna fina continuar clicável.
 *
 * Separação entre segmentos: 2px de VÃO (a superfície do card aparecendo),
 * nunca uma borda.
 *
 * A pilha usa `flex: <valor>` em vez de `height: <n>%`. Com porcentagem, o piso
 * de 3px que mantém "1 OS" visível somava mais que 100% em colunas com muitas
 * categorias e o topo da pilha era cortado — some uma categoria inteira do
 * gráfico. O flexbox reparte a altura disponível (já descontados os vãos) e
 * encolhe os grandes para caber o mínimo dos pequenos: nada estoura.
 */
const props = withDefaults(defineProps<{
  pontos: PontoColuna[]
  series: DefCategoria[]
  altura?: string
  rotuloTotal?: string
  /** mostra o rótulo do eixo a cada N colunas (0 = automático) */
  passoRotulo?: number
}>(), {
  altura: 'h-56',
  rotuloTotal: 'OS finalizadas',
  passoRotulo: 0,
})

/** Topo do eixo: um número redondo logo acima do maior valor. Sempre inteiro —
 *  o eixo conta OS, e "2,5 OS" numa marca de grade não quer dizer nada. */
function escalaBonita(max: number): number {
  if (max <= 0) return 1
  const alvo = max * 1.05
  const base = 10 ** Math.floor(Math.log10(alvo))
  for (const passo of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) {
    if (passo * base >= alvo) return Math.max(2, Math.ceil(passo * base))
  }
  return Math.ceil(10 * base)
}

/** A marca do meio é exatamente topo/2. Se der quebrado, mostramos quebrado —
 *  arredondar aqui faria o rótulo mentir sobre onde a linha de grade está. */
function rotuloTick(valor: number): string {
  return Number.isInteger(valor)
    ? numero(valor)
    : valor.toLocaleString('pt-BR', { maximumFractionDigits: 1 })
}

const maximo = computed(() => Math.max(0, ...props.pontos.map(p => p.total)))
const topo = computed(() => escalaBonita(maximo.value))

/** 3 marcas no eixo. Sem dado nenhum, só o zero ganha rótulo (senão sairia
 *  "1 / 1 / 0", que é o arredondamento de uma escala que não existe). */
const ticks = computed(() =>
  [topo.value, topo.value / 2, 0].map(valor => ({
    valor,
    rotulo: maximo.value > 0 ? rotuloTick(valor) : (valor === 0 ? '0' : ''),
  })),
)

const passo = computed(() => {
  if (props.passoRotulo > 0) return props.passoRotulo
  return Math.max(1, Math.ceil(props.pontos.length / 24))
})

/** Segmentos visíveis (valor > 0) de baixo para cima. Quem reparte a altura é o
 *  flexbox (`flex-grow` = valor); a escala do eixo vem da altura do container
 *  (total/topo). */
function segmentos(ponto: PontoColuna) {
  return props.series
    .map(s => ({ serie: s, valor: ponto.valores[s.chave] ?? 0 }))
    .filter(x => x.valor > 0)
    .map((x, i, todos) => ({ ...x, topoDaPilha: i === todos.length - 1 }))
}

const ativo = ref<number | null>(null)
const pontoAtivo = computed(() => (ativo.value === null ? null : props.pontos[ativo.value] ?? null))

/** Ancora o tooltip na coluna sem deixá-lo sair do card nas pontas. */
const estiloTooltip = computed(() => {
  const i = ativo.value
  const n = props.pontos.length
  if (i === null || !n) return {}
  const centro = ((i + 0.5) / n) * 100
  if (i < n / 4) return { left: `${centro}%`, transform: 'translateX(-15%)' }
  if (i > (n * 3) / 4) return { left: `${centro}%`, transform: 'translateX(-85%)' }
  return { left: `${centro}%`, transform: 'translateX(-50%)' }
})

const detalheAtivo = computed(() => {
  const p = pontoAtivo.value
  if (!p) return []
  return props.series
    .map(s => ({ serie: s, valor: p.valores[s.chave] ?? 0 }))
    .filter(x => x.valor > 0)
})
</script>

<template>
  <div class="relative select-none" @mouseleave="ativo = null">
    <div class="flex" :class="altura">
      <!-- eixo Y -->
      <div class="w-9 shrink-0 flex flex-col justify-between text-[11px] text-dimmed tabular-nums text-right pr-1.5">
        <span
          v-for="t in ticks"
          :key="t.valor"
          class="leading-none -translate-y-1/2 first:translate-y-0 last:-translate-y-full"
        >{{ t.rotulo }}</span>
      </div>

      <!-- área do gráfico -->
      <div class="relative grow min-w-0">
        <!-- linhas de grade (fio de cabelo, recessivas) -->
        <div class="absolute inset-0 flex flex-col justify-between pointer-events-none">
          <span v-for="t in ticks" :key="t.valor" class="block h-px w-full" :style="{ backgroundColor: 'var(--viz-grade)' }" />
        </div>

        <div class="absolute inset-0 flex items-end gap-px">
          <div
            v-for="(p, i) in pontos"
            :key="p.chave"
            class="grow shrink basis-0 h-full flex flex-col justify-end items-center cursor-default rounded-sm transition-colors"
            :class="ativo === i ? 'bg-elevated' : ''"
            @mouseenter="ativo = i"
          >
            <!-- valor só no pico: rotular toda coluna vira ruído -->
            <span
              v-if="p.total === maximo && maximo > 0"
              class="text-[10px] text-muted tabular-nums leading-none mb-1"
            >{{ numero(p.total) }}</span>

            <div
              class="w-full max-w-6 flex flex-col-reverse gap-[2px]"
              :style="{ height: `${(p.total / topo) * 100}%`, opacity: p.atenuado ? 0.7 : 1 }"
            >
              <span
                v-for="seg in segmentos(p)"
                :key="seg.serie.chave"
                class="block w-full min-h-[3px]"
                :class="seg.topoDaPilha ? 'rounded-t-[4px]' : ''"
                :style="{ flex: `${seg.valor} 1 0`, backgroundColor: seg.serie.cor }"
              />
            </div>
            <!-- dia/hora sem nenhuma OS: um traço para o vazio não sumir -->
            <span v-if="p.total === 0" class="w-full max-w-6 h-0.5 rounded-full bg-accented/60" />
          </div>
        </div>
      </div>
    </div>

    <!-- eixo X -->
    <div class="flex mt-1.5">
      <div class="w-9 shrink-0" />
      <div class="grow min-w-0 flex gap-px">
        <div
          v-for="(p, i) in pontos"
          :key="p.chave"
          class="grow shrink basis-0 text-center text-[10px] tabular-nums truncate"
          :class="ativo === i ? 'text-default font-medium' : 'text-dimmed'"
        >
          {{ i % passo === 0 || ativo === i ? p.eixo : '' }}
        </div>
      </div>
    </div>

    <!-- tooltip -->
    <div
      v-if="pontoAtivo"
      class="absolute -top-1 z-10 pointer-events-none min-w-40 max-w-64 rounded-lg border border-default bg-default shadow-lg p-2.5 text-xs"
      :style="estiloTooltip"
    >
      <p class="font-medium text-default">{{ pontoAtivo.titulo }}</p>
      <p v-if="pontoAtivo.sub" class="text-muted">{{ pontoAtivo.sub }}</p>
      <p class="mt-1 mb-1.5 text-default">
        <strong class="tabular-nums">{{ numero(pontoAtivo.total) }}</strong> {{ rotuloTotal }}
      </p>
      <ul v-if="detalheAtivo.length" class="space-y-0.5">
        <li v-for="d in detalheAtivo" :key="d.serie.chave" class="flex items-center gap-1.5">
          <span class="size-2 rounded-full shrink-0" :style="{ backgroundColor: d.serie.cor }" />
          <span class="text-muted grow truncate">{{ d.serie.curto }}</span>
          <span class="tabular-nums text-default">{{ numero(d.valor) }}</span>
        </li>
      </ul>
      <p v-else class="text-muted">Nada finalizado.</p>
    </div>
  </div>
</template>
