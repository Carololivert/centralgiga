<script setup lang="ts">
import type { Olt } from '~/types/monitor'

defineProps<{ olt: Olt }>()
</script>

<template>
  <div
    class="rounded-xl border bg-elevated/50 p-4"
    :class="olt.quente ? 'border-error/40' : 'border-default'"
  >
    <div class="flex items-center justify-between gap-2">
      <p class="text-sm font-medium truncate">
        {{ olt.nome }}
      </p>
      <UIcon
        name="i-lucide-server"
        class="size-4 shrink-0"
        :class="olt.quente ? 'text-error' : 'text-muted'"
      />
    </div>

    <div class="mt-2 flex items-end gap-1">
      <span
        class="text-3xl font-bold tabular-nums leading-none"
        :class="olt.quente ? 'text-error' : ''"
      >{{ olt.temp_num ?? '?' }}</span>
      <span class="text-sm text-muted mb-0.5">°C</span>
      <UIcon v-if="olt.quente" name="i-lucide-flame" class="size-5 text-error mb-0.5" />
    </div>

    <p class="mt-1 text-xs text-muted truncate">
      uptime {{ olt.uptime || '—' }}
    </p>
  </div>
</template>
