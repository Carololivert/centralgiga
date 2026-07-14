<script setup lang="ts">
type Tone = 'error' | 'warning' | 'info' | 'neutral'

const props = defineProps<{
  title: string
  value: number
  sub?: string
  icon?: string
  tone?: Tone
}>()

const valueColor = computed(() => ({
  error: 'text-error',
  warning: 'text-warning',
  info: 'text-info',
  neutral: '',
}[props.tone ?? 'neutral']))

const iconColor = computed(() => ({
  error: 'text-error',
  warning: 'text-warning',
  info: 'text-info',
  neutral: 'text-muted',
}[props.tone ?? 'neutral']))
</script>

<template>
  <div class="rounded-xl border border-default bg-elevated/50 p-4">
    <div class="flex items-center justify-between gap-2">
      <p class="text-xs uppercase tracking-wide text-muted truncate">
        {{ title }}
      </p>
      <UIcon v-if="icon" :name="icon" class="size-5 shrink-0" :class="iconColor" />
    </div>
    <p class="mt-2 text-3xl font-bold tabular-nums" :class="valueColor">
      {{ value }}
    </p>
    <p v-if="sub" class="mt-1 text-xs text-muted">
      {{ sub }}
    </p>
  </div>
</template>
