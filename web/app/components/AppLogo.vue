<script setup lang="ts">
withDefaults(defineProps<{ collapsed?: boolean; size?: 'sm' | 'lg' }>(), {
  collapsed: false,
  size: 'sm',
})
</script>

<template>
  <span class="flex items-center gap-2.5 font-semibold tracking-tight">
    <!-- login: boneco inteiro -->
    <img
      v-if="size === 'lg'"
      src="/boneco-giganet.png"
      alt="Giganet"
      class="size-24 object-contain shrink-0"
    >
    <!-- sidebar: cabeça em avatar redondo -->
    <span
      v-else
      class="size-14 rounded-full overflow-hidden ring-1 ring-(--ui-border) bg-(--ui-bg-elevated) shrink-0"
    >
      <img src="/boneco-cabeca.png" alt="Giganet" class="size-full object-cover">
    </span>

    <span v-if="!collapsed" class="flex flex-col leading-tight">
      <span :class="size === 'lg' ? 'text-xl' : 'text-base'">Central Giganet</span>
      <span class="text-xs text-muted font-normal">Automações</span>
    </span>
  </span>
</template>
