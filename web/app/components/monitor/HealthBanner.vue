<script setup lang="ts">
import type { Health } from '~/types/monitor'

const props = defineProps<{ health: Health }>()
const meta = computed(() => healthMeta(props.health))

const tone = computed(() => ({
  success: 'bg-success/10 border-success/30 text-success',
  warning: 'bg-warning/10 border-warning/30 text-warning',
  error: 'bg-error/10 border-error/40 text-error',
}[meta.value.color]))

const dot = computed(() => ({
  success: 'bg-success',
  warning: 'bg-warning',
  error: 'bg-error',
}[meta.value.color]))
</script>

<template>
  <div class="flex items-center gap-3 rounded-xl border px-4 py-3" :class="tone">
    <span class="relative flex size-3 shrink-0">
      <span
        v-if="health === 'crit'"
        class="absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping"
        :class="dot"
      />
      <span class="relative inline-flex rounded-full size-3" :class="dot" />
    </span>
    <UIcon :name="meta.icon" class="size-5 shrink-0" />
    <div class="min-w-0">
      <p class="font-semibold leading-tight">
        {{ meta.titulo }}
      </p>
      <p class="text-sm opacity-90 leading-tight truncate">
        {{ meta.descricao }}
      </p>
    </div>
  </div>
</template>
