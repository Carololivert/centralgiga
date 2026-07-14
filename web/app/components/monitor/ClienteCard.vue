<script setup lang="ts">
import type { Cliente } from '~/types/monitor'

const props = defineProps<{ cliente: Cliente }>()

const statusBadge = computed(() => {
  const s = props.cliente.contrato_status
  if (s === 'Ativo') return { color: 'success' as const, label: 'Ativo' }
  if (s === 'Cancelado') return { color: 'error' as const, label: 'Cancelado' }
  return { color: 'neutral' as const, label: 'sem SGP' }
})

const ativo = computed(() => props.cliente.contrato_status === 'Ativo')
const cancelado = computed(() => props.cliente.contrato_status === 'Cancelado')
const caiu = computed(() =>
  props.cliente.onu_status && props.cliente.onu_status !== 'Online' && props.cliente.caiu_fmt
    ? props.cliente.caiu_fmt
    : null,
)
</script>

<template>
  <div
    class="px-4 py-3"
    :class="[ativo ? 'shadow-[inset_3px_0_0_var(--ui-success)]' : '', cancelado ? 'opacity-55' : '']"
  >
    <div class="flex items-center flex-wrap gap-x-2 gap-y-1">
      <span class="font-medium">{{ cliente.nome || '(sem nome)' }}</span>
      <UBadge :color="statusBadge.color" variant="subtle" size="sm" :label="statusBadge.label" />
      <span class="text-sm text-muted">·</span>
      <span class="text-sm font-medium" :class="onuColor(cliente.onu_status)">
        {{ cliente.onu_status || '—' }}
      </span>
      <span v-if="caiu" class="text-xs text-muted">caiu {{ caiu }}</span>
    </div>

    <div class="mt-1 text-xs text-muted space-y-0.5">
      <p>
        login: <span class="text-default">{{ cliente.name_olt || '-' }}</span>
        · contrato {{ cliente.contrato_id || '-' }}
        <template v-if="cliente.plano"> · {{ cliente.plano }}</template>
      </p>
      <p>{{ cliente.endereco || '(sem endereço no SGP)' }}</p>
      <p v-if="cliente.telefones?.length">
        tel: {{ cliente.telefones.join(', ') }}
      </p>
    </div>
  </div>
</template>
