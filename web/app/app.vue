<script setup lang="ts">
// locale pt-BR: nomes de meses/dias do calendário (e demais componentes) em português
import { pt_br } from '@nuxt/ui/locale'
</script>

<template>
  <UApp :locale="pt_br">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
