<script setup lang="ts">
import type { PonRef, PonResp } from '~/types/monitor'

const props = defineProps<{ pon: PonRef | null }>()
const open = defineModel<boolean>('open', { default: false })

const { fetchPon } = useMonitor()

const janela = ref(1)
const dados = ref<PonResp | null>(null)
const carregando = ref(false)
const erro = ref<string | null>(null)

const titulo = computed(() => (props.pon ? `${props.pon.regiao}` : 'PON'))
const subtitulo = computed(() =>
  props.pon ? `OLT ${props.pon.olt} · b${props.pon.board}/p${props.pon.port}` : '',
)

async function carregar() {
  if (!props.pon) return
  carregando.value = true
  erro.value = null
  try {
    dados.value = await fetchPon(props.pon, janela.value)
    if (!dados.value.ok) erro.value = dados.value.erro || 'Erro ao consultar a PON'
  } catch (e) {
    erro.value = (e as Error)?.message || 'Falha ao cruzar com o SGP'
  } finally {
    carregando.value = false
  }
}

// Ao abrir com uma PON nova: zera e busca. (A janela NÃO é resetada aqui de
// propósito — evita disparar os dois watchers e bater duas vezes no SGP.)
watch(() => [open.value, props.pon] as const, ([aberto]) => {
  if (aberto && props.pon) {
    dados.value = null
    carregar()
  }
})
watch(janela, () => {
  if (open.value && props.pon) carregar()
})

const vazio = computed(() =>
  dados.value && !dados.value.grupos?.length && !dados.value.sem_hora?.length,
)
</script>

<template>
  <UModal
    v-model:open="open"
    :title="titulo"
    :description="subtitulo"
    :ui="{ content: 'sm:max-w-2xl', body: 'sm:p-0' }"
  >
    <template #body>
      <!-- barra de resumo + janela -->
      <div class="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-default text-sm">
        <template v-if="dados?.ok">
          <span class="text-muted">
            <b class="text-default tabular-nums">{{ dados.total_pon }}</b> na PON ·
            <b class="text-default tabular-nums">{{ dados.down }}</b> caído(s) ·
            <b class="text-warning tabular-nums">{{ dados.ativos_down }}</b> ativo(s) caído
          </span>
          <UBadge
            v-if="dados.capped"
            color="neutral"
            variant="subtle"
            size="sm"
            :label="`amostra ${dados.clientes.length}`"
          />
        </template>
        <span v-else-if="carregando" class="text-muted">carregando…</span>
        <span v-else-if="erro" class="text-error">falha ao carregar</span>

        <label class="ml-auto flex items-center gap-1.5 text-xs text-muted" title="margem em minutos p/ agrupar quedas do mesmo momento">
          janela ±
          <UInput
            v-model.number="janela"
            type="number"
            :min="0"
            :max="60"
            size="xs"
            class="w-16"
          />
          min
        </label>
      </div>

      <!-- corpo -->
      <div class="max-h-[60vh] overflow-y-auto">
        <div v-if="carregando" class="flex items-center justify-center gap-2 py-10 text-muted">
          <UIcon name="i-lucide-loader-circle" class="size-5 animate-spin" />
          cruzando com o SGP…
        </div>

        <div v-else-if="erro" class="py-10 text-center text-error text-sm">
          {{ erro }}
        </div>

        <div v-else-if="vazio" class="py-10 text-center text-muted">
          sem quedas nesta PON agora 🎉
        </div>

        <div v-else-if="dados" class="p-4 space-y-3">
          <!-- grupos por motivo + janela -->
          <div
            v-for="(g, gi) in dados.grupos"
            :key="`g-${gi}`"
            class="rounded-lg border border-default overflow-hidden"
          >
            <div class="flex flex-wrap items-center gap-2 px-3 py-2 bg-elevated/60 text-sm">
              <UBadge :color="motivoColor(g.motivo)" variant="subtle" size="sm" :label="g.motivo_label" />
              <b>{{ g.n }} queda{{ g.n > 1 ? 's' : '' }}</b>
              <span class="text-muted">· caiu ~{{ g.caiu_fmt || '—' }}</span>
              <span v-if="g.span_min" class="text-xs text-muted">(±{{ g.span_min }}min)</span>
              <UBadge
                v-if="g.ativos"
                color="success"
                variant="subtle"
                size="sm"
                class="ml-auto"
                :label="`${g.ativos} ativo${g.ativos > 1 ? 's' : ''}`"
              />
              <span v-else class="ml-auto text-xs text-muted">só cancelados</span>
            </div>
            <div class="divide-y divide-default">
              <MonitorClienteCard v-for="(c, ci) in g.clientes" :key="`c-${ci}`" :cliente="c" />
            </div>
          </div>

          <!-- sem horário registrado -->
          <div v-if="dados.sem_hora?.length" class="rounded-lg border border-default overflow-hidden">
            <div class="px-3 py-2 bg-elevated/60 text-sm text-muted">
              sem horário registrado · {{ dados.sem_hora.length }}
            </div>
            <div class="divide-y divide-default">
              <MonitorClienteCard v-for="(c, ci) in dados.sem_hora" :key="`s-${ci}`" :cliente="c" />
            </div>
          </div>
        </div>
      </div>
    </template>
  </UModal>
</template>
