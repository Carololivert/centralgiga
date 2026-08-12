<script setup lang="ts">
import type { CategoriaOS } from '~/types/producao'
import type { DefCategoria } from '~/utils/producao'

/**
 * Legenda das séries. Sempre presente quando há 2+ séries — é o canal de
 * identidade que não depende de acertar a cor no olho (e três das cores do tema
 * claro ficam abaixo de 3:1 de contraste, então a legenda não é enfeite).
 *
 * Clicável: some/volta a categoria nos gráficos. A cor NUNCA muda com o
 * filtro — cada categoria carrega o seu slot do começo ao fim.
 */
const props = defineProps<{
  series: DefCategoria[]
  /** categorias visíveis; ausente = todas visíveis e sem interação */
  visiveis?: CategoriaOS[]
  totais?: Partial<Record<CategoriaOS, number>>
}>()

const emit = defineEmits<{ alternar: [CategoriaOS] }>()

const interativa = computed(() => props.visiveis !== undefined)

function ativa(chave: CategoriaOS) {
  return !props.visiveis || props.visiveis.includes(chave)
}
</script>

<template>
  <ul class="flex flex-wrap items-center gap-x-4 gap-y-1.5">
    <li v-for="s in series" :key="s.chave">
      <component
        :is="interativa ? 'button' : 'span'"
        :type="interativa ? 'button' : undefined"
        class="inline-flex items-center gap-1.5 text-xs"
        :class="[
          interativa ? 'cursor-pointer hover:opacity-80 transition-opacity' : '',
          ativa(s.chave) ? 'text-muted' : 'text-dimmed line-through',
        ]"
        :aria-pressed="interativa ? ativa(s.chave) : undefined"
        @click="interativa && emit('alternar', s.chave)"
      >
        <span
          class="size-2.5 rounded-full shrink-0"
          :style="{ backgroundColor: s.cor, opacity: ativa(s.chave) ? 1 : 0.35 }"
          aria-hidden="true"
        />
        {{ s.curto }}
        <span v-if="totais && totais[s.chave] !== undefined" class="tabular-nums font-medium">
          {{ numero(totais[s.chave]) }}
        </span>
      </component>
    </li>
  </ul>
</template>
