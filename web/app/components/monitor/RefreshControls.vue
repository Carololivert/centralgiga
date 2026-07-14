<script setup lang="ts">
// Controles de atualização (canto direito da navbar): selo DEMO, horário do
// snapshot, contagem regressiva e botão "atualizar agora".
const { geradoEm, countdown, carregando, demo, refresh, REFRESH_SECS } = useMonitor()

const dasharray = 2 * Math.PI * 9 // r = 9
const dashoffset = computed(() => dasharray * (1 - countdown.value / REFRESH_SECS))
</script>

<template>
  <div class="flex items-center gap-2 sm:gap-3">
    <UBadge
      v-if="demo"
      color="warning"
      variant="subtle"
      size="sm"
      icon="i-lucide-flask-conical"
      label="DEMO"
      title="Dados de demonstração (sem SmartOLT/SGP configurados)"
    />

    <div class="hidden sm:flex flex-col items-end leading-tight">
      <span class="text-xs text-muted">
        <template v-if="geradoEm">atualizado {{ geradoEm }}</template>
        <template v-else>aguardando dados…</template>
      </span>
      <span class="text-[11px] text-dimmed">próxima em {{ countdown }}s</span>
    </div>

    <!-- anel de contagem regressiva -->
    <svg class="size-6 -rotate-90 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" fill="none" stroke="var(--ui-border)" stroke-width="3" />
      <circle
        cx="12" cy="12" r="9" fill="none"
        stroke="var(--ui-primary)" stroke-width="3" stroke-linecap="round"
        :stroke-dasharray="dasharray" :stroke-dashoffset="dashoffset"
        style="transition: stroke-dashoffset 1s linear"
      />
    </svg>

    <UButton
      icon="i-lucide-refresh-cw"
      color="primary"
      variant="soft"
      :loading="carregando"
      label="Atualizar"
      @click="refresh"
    />
  </div>
</template>
