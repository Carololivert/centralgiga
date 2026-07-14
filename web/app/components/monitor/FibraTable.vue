<script setup lang="ts">
import type { EventoFibra } from '~/types/monitor'

defineProps<{ eventos: EventoFibra[] }>()
const emit = defineEmits<{ open: [EventoFibra] }>()

function rowAccent(kind: string) {
  return kind === 'los'
    ? 'shadow-[inset_3px_0_0_var(--ui-error)]'
    : 'shadow-[inset_3px_0_0_var(--ui-warning)]'
}
</script>

<template>
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead class="text-muted text-[11px] uppercase tracking-wide">
        <tr class="text-left border-b border-default">
          <th class="py-2 pl-3 pr-3 font-medium">
            Tipo
          </th>
          <th class="py-2 px-3 font-medium">
            Região
          </th>
          <th class="py-2 px-3 font-medium">
            OLT
          </th>
          <th class="py-2 px-3 font-medium">
            PON
          </th>
          <th class="py-2 px-3 font-medium">
            Afetadas
          </th>
          <th class="py-2 px-3 font-medium">
            Motivo
          </th>
          <th class="py-2 px-3 font-medium">
            Caiu em
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!eventos.length">
          <td colspan="7" class="py-8 text-center text-muted">
            nenhuma PON afetada 🎉
          </td>
        </tr>
        <tr
          v-for="(e, i) in eventos"
          :key="`${e.olt_id}-${e.board}-${e.port}-${i}`"
          class="border-b border-default/60 cursor-pointer hover:bg-elevated/60 transition-colors"
          :class="rowAccent(e.kind)"
          @click="emit('open', e)"
        >
          <td class="py-2.5 pl-3 pr-3 whitespace-nowrap">
            <UBadge
              :color="e.kind === 'los' ? 'error' : 'warning'"
              variant="subtle"
              size="sm"
              :label="e.kind === 'los' ? 'TOTAL' : 'parcial'"
            />
            <UBadge v-if="e.novo" color="error" variant="solid" size="sm" label="NOVO" class="ml-1" />
          </td>
          <td class="py-2.5 px-3">
            <p class="truncate max-w-[16rem]">
              {{ e.regiao }}
            </p>
            <p v-if="e.cidade" class="text-xs text-muted truncate max-w-[16rem]">
              {{ e.cidade }}
            </p>
          </td>
          <td class="py-2.5 px-3 whitespace-nowrap text-muted">
            {{ e.olt }}
          </td>
          <td class="py-2.5 px-3 whitespace-nowrap tabular-nums">
            b{{ e.board }}/p{{ e.port }}
          </td>
          <td class="py-2.5 px-3 whitespace-nowrap">
            <div class="flex items-center gap-2">
              <span class="tabular-nums">{{ e.los + e.power + e.offline }}/{{ e.total_onus }}</span>
              <span class="inline-block h-1.5 w-16 rounded-full bg-muted overflow-hidden">
                <span class="block h-full rounded-full bg-error" :style="{ width: barWidth(e.percent) + '%' }" />
              </span>
              <span class="text-xs text-muted tabular-nums">{{ e.percent }}%</span>
            </div>
          </td>
          <td class="py-2.5 px-3 whitespace-nowrap text-xs text-muted tabular-nums">
            LOS {{ e.los }} · pwr {{ e.power }} · off {{ e.offline }}
          </td>
          <td class="py-2.5 px-3 whitespace-nowrap">
            <p>{{ e.caiu_fmt || '—' }}</p>
            <p class="text-xs text-muted">
              {{ e.idade }} atrás
            </p>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
