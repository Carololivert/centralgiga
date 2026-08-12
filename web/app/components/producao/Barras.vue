<script setup lang="ts">
import type { LinhaBarra } from '~/types/producao'
import type { DefCategoria } from '~/utils/producao'

/**
 * Barras horizontais empilhadas — ranking por POP, por equipe, por categoria.
 * Horizontal porque os rótulos são longos ("Fibra 585 - Itapoã Park lote 11…")
 * e em coluna eles teriam de virar na diagonal, que ninguém lê.
 *
 * Cada linha mostra o total ao lado e a quebra em `sub` — o número fica na
 * tela, não escondido atrás do mouse. O `title` da barra traz a quebra completa
 * para quem passar o cursor.
 */
const props = withDefaults(defineProps<{
  linhas: LinhaBarra[]
  series: DefCategoria[]
  /** classe de largura da coluna de rótulos */
  larguraRotulo?: string
}>(), {
  larguraRotulo: 'w-40 sm:w-56',
})

const maximo = computed(() => Math.max(1, ...props.linhas.map(l => l.total)))

/** Quem reparte a largura é o flexbox (`flex-grow` = valor), como em Colunas:
 *  com porcentagem + piso de 3px, uma linha com muitas categorias somava mais
 *  que a barra e a última cor era cortada. */
function segmentos(linha: LinhaBarra) {
  return props.series
    .map(s => ({ serie: s, valor: linha.valores[s.chave] ?? 0 }))
    .filter(x => x.valor > 0)
    .map((x, i, todos) => ({ ...x, fimDaBarra: i === todos.length - 1 }))
}

function descricao(linha: LinhaBarra) {
  const partes = props.series
    .map(s => ({ s, v: linha.valores[s.chave] ?? 0 }))
    .filter(x => x.v > 0)
    .map(x => `${x.s.curto}: ${x.v}`)
  return `${linha.rotulo} — ${partes.join(' · ') || 'sem OS'}`
}
</script>

<template>
  <ul class="space-y-2">
    <li
      v-for="l in linhas"
      :key="l.chave"
      class="flex items-center gap-3 text-sm"
    >
      <div class="shrink-0 min-w-0" :class="larguraRotulo">
        <p class="truncate text-default" :title="l.rotulo">{{ l.rotulo }}</p>
        <p v-if="l.sub" class="truncate text-xs text-muted">{{ l.sub }}</p>
      </div>

      <div class="grow min-w-0 h-5" :title="descricao(l)">
        <div
          class="h-full flex gap-[2px] items-stretch"
          :style="{ width: `${(l.total / maximo) * 100}%` }"
        >
          <span
            v-for="seg in segmentos(l)"
            :key="seg.serie.chave"
            class="block h-full min-w-[3px]"
            :class="seg.fimDaBarra ? 'rounded-r-[4px]' : ''"
            :style="{ flex: `${seg.valor} 1 0`, backgroundColor: seg.serie.cor }"
          />
        </div>
      </div>

      <span class="shrink-0 w-10 text-right tabular-nums font-medium text-default">
        {{ numero(l.total) }}
      </span>
    </li>
  </ul>
</template>
