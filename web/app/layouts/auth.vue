<script setup lang="ts">
// Tela de login: centralizada, branco + azul.
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-4 bg-muted/30">
    <div class="absolute top-4 right-4">
      <UColorModeButton />
    </div>
    <div class="w-full max-w-sm">
      <slot />
    </div>
  </div>
</template>
