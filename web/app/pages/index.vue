<script setup lang="ts">
/**
 * Porta de entrada da Central.
 *
 * Quem tem acesso ao painel de **Produção** cai direto nele — é o que a
 * supervisão quer ver ao abrir o sistema (como o dia está indo). Quem não tem
 * (atendente) vai para a grade de sistemas, que continua em /sistemas.
 *
 * A decisão sai da tabela `systems`, não do cargo escrito na mão: a RLS já
 * devolve a linha 'producao' só para quem pode vê-la. Assim, se um dia o painel
 * for desativado ou liberado para outro cargo, esta tela acompanha sozinha —
 * e ninguém é mandado para uma página que lhe daria 403.
 */
definePageMeta({ middleware: 'role' })

const client = useSupabaseClient()

const { data: destino } = await useAsyncData('inicio-destino', async () => {
  const { data } = await client
    .from('systems')
    .select('slug')
    .eq('slug', 'producao')
    .eq('active', true)
    .maybeSingle()
  return data ? '/producao' : '/sistemas'
})

await navigateTo(destino.value ?? '/sistemas', { replace: true })
</script>

<template>
  <div class="flex justify-center py-24 text-muted">
    <UIcon name="i-lucide-loader-circle" class="size-7 animate-spin" />
  </div>
</template>
