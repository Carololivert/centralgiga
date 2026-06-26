<script setup lang="ts">
const props = defineProps<{ dados: any }>()

const contagem = computed(() => props.dados?.contagem ?? {})
const lista = computed<any[]>(() => props.dados?.os ?? [])
const aberto = ref<string | null>(null)

const corBadge: Record<string, any> = {
  ok: 'success',
  atencao: 'warning',
  problema: 'error',
  erro: 'error',
}
const corIcone: Record<string, string> = {
  ok: 'text-success',
  atencao: 'text-warning',
  problema: 'text-error',
  erro: 'text-error',
}
const icone: Record<string, string> = {
  ok: 'i-lucide-check',
  atencao: 'i-lucide-alert-triangle',
  problema: 'i-lucide-x',
  erro: 'i-lucide-circle-alert',
}
</script>

<template>
  <div>
    <div class="flex flex-wrap gap-2 mb-3">
      <UBadge color="neutral" variant="subtle" :label="`${lista.length} OS · ${dados.equipe}`" />
      <UBadge v-if="contagem.ok" color="success" variant="subtle" :label="`${contagem.ok} ok`" />
      <UBadge v-if="contagem.atencao" color="warning" variant="subtle" :label="`${contagem.atencao} atenção`" />
      <UBadge v-if="contagem.problema" color="error" variant="subtle" :label="`${contagem.problema} problema`" />
      <UBadge v-if="contagem.erro" color="error" variant="soft" :label="`${contagem.erro} erro`" />
    </div>

    <div v-if="lista.length" class="border border-(--ui-border) rounded-lg divide-y divide-(--ui-border)">
      <div v-for="o in lista" :key="o.os_numero" class="p-2.5">
        <div class="flex items-center gap-2">
          <UIcon :name="icone[o.status] || icone.erro" :class="[corIcone[o.status] || corIcone.erro, 'size-4 shrink-0']" />
          <span class="font-medium text-sm">OS {{ o.os_numero }}</span>
          <span class="text-xs text-(--ui-text-muted)">· {{ o.responsavel }}</span>
          <span v-if="o.cliente" class="text-xs text-(--ui-text-muted) truncate max-w-[40%]">· {{ o.cliente }}</span>
          <a
            v-if="o.os_url"
            :href="o.os_url"
            target="_blank"
            rel="noreferrer"
            class="text-xs text-primary ml-1"
            @click.stop
          >abrir ↗</a>
          <span class="ml-auto" />
          <UBadge
            v-if="o.alerta_mac"
            color="error"
            variant="soft"
            size="sm"
            icon="i-lucide-radio"
            label="MAC"
            title="Troca de equipamento sem limpeza/ativação do MAC"
          />
          <UButton
            v-if="o.problemas?.length"
            size="xs"
            color="neutral"
            variant="ghost"
            :icon="aberto === o.os_numero ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
            :label="String(o.problemas.length)"
            @click="aberto = aberto === o.os_numero ? null : o.os_numero"
          />
        </div>

        <p class="text-xs text-(--ui-text-muted) mt-1 ml-6">
          <span>{{ o.motivo }}</span>
          <span v-if="o.resumo"> — {{ o.resumo }}</span>
        </p>

        <ul v-if="aberto === o.os_numero && o.problemas?.length" class="mt-2 ml-6 space-y-1.5">
          <li v-for="(p, i) in o.problemas" :key="i" class="text-xs">
            <UBadge :color="corBadge[o.status] || 'neutral'" variant="soft" size="sm" :label="p.tipo" class="mr-1" />
            {{ p.descricao }}
            <span v-if="p.pergunta" class="text-(--ui-text-muted)"> — {{ p.pergunta }}</span>
          </li>
        </ul>
      </div>
    </div>
    <p v-else class="text-sm text-(--ui-text-muted)">Nenhuma OS encontrada para a equipe.</p>
  </div>
</template>
