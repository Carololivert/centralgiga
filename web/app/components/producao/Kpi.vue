<script setup lang="ts">
/**
 * Número em destaque do painel (instalações, remoções, total…).
 *
 * `destaque` marca o número-herói da tela — só UM por view.
 * `sentido`:
 *   'positivo' → subir é bom (instalações): verde para cima, vermelho para baixo;
 *   'neutro'   → subir não é bom nem ruim (remoções, corretivas): só a seta,
 *                em texto secundário. Pintar de vermelho um mês com mais
 *                remoções seria um julgamento que o dado não sustenta.
 */
const props = withDefaults(defineProps<{
  rotulo: string
  valor: number
  sub?: string
  cor?: string
  icone?: string
  /** variação % contra o período anterior (null = sem base de comparação) */
  variacao?: number | null
  variacaoRotulo?: string
  sentido?: 'positivo' | 'neutro'
  destaque?: boolean
}>(), {
  sentido: 'neutro',
  destaque: false,
  variacao: null,
})

const seta = computed(() => {
  if (props.variacao === null || props.variacao === 0) return 'i-lucide-minus'
  return props.variacao > 0 ? 'i-lucide-trending-up' : 'i-lucide-trending-down'
})

const classeVariacao = computed(() => {
  if (props.variacao === null || props.sentido === 'neutro') return 'text-muted'
  if (props.variacao === 0) return 'text-muted'
  return props.variacao > 0 ? 'text-success' : 'text-error'
})
</script>

<template>
  <div class="rounded-xl border border-default bg-elevated/40 p-4 flex flex-col gap-1">
    <div class="flex items-center gap-2 text-sm text-muted">
      <span
        v-if="cor"
        class="size-2.5 rounded-full shrink-0"
        :style="{ backgroundColor: cor }"
        aria-hidden="true"
      />
      <UIcon v-else-if="icone" :name="icone" class="size-4 shrink-0" />
      <span class="truncate">{{ rotulo }}</span>
    </div>

    <p
      class="font-semibold text-default leading-none"
      :class="destaque ? 'text-5xl mt-1' : 'text-3xl'"
    >
      {{ numero(valor) }}
    </p>

    <div class="flex items-baseline gap-2 flex-wrap text-xs mt-0.5">
      <span
        v-if="variacao !== null"
        class="inline-flex items-center gap-0.5 font-medium"
        :class="classeVariacao"
      >
        <UIcon :name="seta" class="size-3.5" />{{ textoVariacao(variacao) }}
      </span>
      <span v-if="variacaoRotulo && variacao !== null" class="text-muted">{{ variacaoRotulo }}</span>
      <span v-if="sub" class="text-muted">{{ sub }}</span>
    </div>
  </div>
</template>
