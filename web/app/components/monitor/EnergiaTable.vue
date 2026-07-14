<script setup lang="ts">
import type { EventoEnergia } from '~/types/monitor'

defineProps<{ eventos: EventoEnergia[] }>()
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
            Clientes
          </th>
          <th class="py-2 px-3 font-medium">
            Caiu em
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!eventos.length">
          <td colspan="5" class="py-8 text-center text-muted">
            nada por aqui
          </td>
        </tr>
        <tr
          v-for="(e, i) in eventos"
          :key="`${e.regiao}-${e.kind}-${i}`"
          class="border-b border-default/60"
        >
          <td class="py-2.5 pl-3 pr-3 whitespace-nowrap">
            <UBadge
              :color="e.kind === 'power' ? 'info' : 'neutral'"
              variant="subtle"
              size="sm"
              :icon="e.kind === 'power' ? 'i-lucide-zap' : 'i-lucide-power-off'"
              :label="e.kind === 'power' ? 'energia' : 'offline'"
            />
          </td>
          <td class="py-2.5 px-3">
            <p class="truncate max-w-[18rem]">
              {{ e.regiao }}
            </p>
            <p v-if="e.cidade" class="text-xs text-muted truncate max-w-[18rem]">
              {{ e.cidade }}
            </p>
          </td>
          <td class="py-2.5 px-3 whitespace-nowrap text-muted">
            {{ e.olt }}
          </td>
          <td class="py-2.5 px-3 whitespace-nowrap tabular-nums">
            {{ e.subs }}
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
