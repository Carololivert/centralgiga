<script setup lang="ts">
definePageMeta({ layout: false })
const user = useSupabaseUser()
watch(
  user,
  () => {
    if (user.value) navigateTo('/')
  },
  { immediate: true },
)
</script>

<template>
  <div class="min-h-screen grid place-items-center text-(--ui-text-muted)">
    <p>Entrando…</p>
  </div>
</template>
