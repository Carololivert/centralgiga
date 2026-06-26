<script setup lang="ts">
import type { GiganetReview, GiganetStatus } from '~/types/db'

definePageMeta({ middleware: 'role', roles: ['admin'] })

const client = useSupabaseClient()
const toast = useToast()

const { data: reviews, refresh } = await useAsyncData('avaliacoes', async () => {
  const { data } = await client
    .from('giganet_reviews')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(200)
  return (data ?? []) as GiganetReview[]
})

// auto-atualiza (novas avaliações chegam pelo n8n)
let timer: any = null
onMounted(() => {
  timer = setInterval(() => refresh(), 5000)
})
onUnmounted(() => timer && clearInterval(timer))

type View = 'pending' | 'approved' | 'rejected' | 'all'
const view = ref<View>('pending')
const lista = computed(() => (reviews.value ?? []).filter(r => view.value === 'all' || r.status === view.value))
const counts = computed(() => ({
  pending: (reviews.value ?? []).filter(r => r.status === 'pending').length,
  approved: (reviews.value ?? []).filter(r => r.status === 'approved').length,
  rejected: (reviews.value ?? []).filter(r => r.status === 'rejected').length,
  all: (reviews.value ?? []).length,
}))

// texto editável por avaliação (pendente)
const edits = reactive<Record<string, string>>({})
const lastAi = reactive<Record<string, string>>({})
watch(
  reviews,
  (list) => {
    for (const r of list ?? []) {
      if (r.status === 'pending' && (edits[r.id] === undefined || lastAi[r.id] !== r.ai_response)) {
        edits[r.id] = r.final_response ?? r.ai_response
        lastAi[r.id] = r.ai_response
      }
    }
  },
  { immediate: true },
)

const busyId = ref<string | null>(null)
const regenId = ref<string | null>(null)

async function aprovar(r: GiganetReview) {
  busyId.value = r.id
  try {
    await $fetch(`/api/avaliacoes/${r.id}/aprovar`, {
      method: 'POST',
      body: { final_response: edits[r.id] },
    })
    toast.add({ title: 'Aprovada e publicada ✓', color: 'success' })
    await refresh()
  } catch (e: any) {
    toast.add({ title: 'Falha ao aprovar', description: e?.data?.statusMessage || e?.message, color: 'error' })
  } finally {
    busyId.value = null
  }
}

async function rejeitar(r: GiganetReview) {
  busyId.value = r.id
  try {
    await client.from('giganet_reviews')
      .update({ status: 'rejected', final_response: null, decided_at: new Date().toISOString() })
      .eq('id', r.id)
    await client.rpc('registrar_auditoria', { p_action: 'avaliacao-rejeitada', p_detail: { id: r.id } })
    toast.add({ title: 'Rejeitada', color: 'neutral' })
    await refresh()
  } finally {
    busyId.value = null
  }
}

async function regerar(r: GiganetReview) {
  regenId.value = r.id
  try {
    await $fetch(`/api/avaliacoes/${r.id}/regenerar`, { method: 'POST' })
    await refresh()
    toast.add({ title: 'Nova resposta gerada', color: 'success' })
  } catch (e: any) {
    toast.add({ title: 'Falha ao regerar', description: e?.data?.statusMessage || e?.message, color: 'error' })
  } finally {
    regenId.value = null
  }
}

async function salvarRascunho(r: GiganetReview) {
  await client.from('giganet_reviews').update({ final_response: edits[r.id] }).eq('id', r.id)
  toast.add({ title: 'Rascunho salvo', color: 'neutral' })
  await refresh()
}

async function remover(id: string) {
  if (!confirm('Excluir esta avaliação da lista?')) return
  await client.from('giganet_reviews').delete().eq('id', id)
  toast.add({ title: 'Removida', color: 'neutral' })
  await refresh()
}

function estrelas(n: number | null) {
  const c = n ?? 0
  return '★'.repeat(c) + '☆'.repeat(Math.max(0, 5 - c))
}
function fmtDate(iso: string) {
  return new Date(iso).toLocaleString('pt-BR')
}
const badge: Record<GiganetStatus, { label: string, color: any }> = {
  pending: { label: 'pendente', color: 'warning' },
  approved: { label: 'aprovada', color: 'success' },
  rejected: { label: 'rejeitada', color: 'neutral' },
}
</script>

<template>
  <UDashboardPanel id="avaliacoes">
    <template #header>
      <UDashboardNavbar title="Giganet Avaliações" icon="i-lucide-star">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="flex flex-wrap gap-2 mb-5">
        <UButton
          v-for="v in (['pending', 'approved', 'rejected', 'all'] as View[])"
          :key="v"
          :color="view === v ? 'primary' : 'neutral'"
          :variant="view === v ? 'solid' : 'soft'"
          size="sm"
          @click="view = v"
        >
          {{ { pending: 'Pendentes', approved: 'Aprovadas', rejected: 'Rejeitadas', all: 'Tudo' }[v] }}
          ({{ counts[v] }})
        </UButton>
      </div>

      <div v-if="lista.length" class="space-y-4">
        <UCard v-for="r in lista" :key="r.id">
          <div class="flex items-start justify-between gap-3">
            <div>
              <span class="text-amber-500 tracking-widest">{{ estrelas(r.star_rating) }}</span>
              <p class="font-semibold">{{ r.reviewer_name || 'cliente' }}</p>
            </div>
            <div class="text-right">
              <UBadge :color="badge[r.status].color" variant="subtle" size="sm" :label="badge[r.status].label" />
              <p class="text-xs text-muted mt-1">{{ fmtDate(r.created_at) }}</p>
            </div>
          </div>

          <blockquote v-if="r.comment" class="mt-3 text-sm text-muted border-l-2 border-default pl-3 italic">
            {{ r.comment }}
          </blockquote>

          <div class="mt-4">
            <p class="text-xs font-medium text-muted mb-1">
              Resposta {{ r.status === 'pending' ? '· edite se quiser' : '' }}
            </p>
            <UTextarea
              v-if="r.status === 'pending'"
              v-model="edits[r.id]"
              :rows="4"
              autoresize
              class="w-full"
              :disabled="busyId === r.id || regenId === r.id"
            />
            <p v-else class="text-sm whitespace-pre-wrap">{{ r.final_response || r.ai_response }}</p>
          </div>

          <div v-if="r.status === 'pending'" class="flex flex-wrap items-center gap-2 mt-4">
            <UButton
              icon="i-lucide-refresh-cw"
              color="neutral"
              variant="soft"
              size="sm"
              :loading="regenId === r.id"
              label="Regerar com IA"
              :disabled="busyId === r.id"
              @click="regerar(r)"
            />
            <span class="grow" />
            <UButton
              color="error"
              variant="ghost"
              size="sm"
              label="Rejeitar"
              :disabled="busyId === r.id || regenId === r.id"
              @click="rejeitar(r)"
            />
            <UButton
              color="neutral"
              variant="soft"
              size="sm"
              label="Salvar rascunho"
              :disabled="busyId === r.id || regenId === r.id"
              @click="salvarRascunho(r)"
            />
            <UButton
              icon="i-lucide-check"
              size="sm"
              label="Aprovar e publicar"
              :loading="busyId === r.id"
              :disabled="regenId === r.id"
              @click="aprovar(r)"
            />
          </div>
          <div v-else class="flex justify-end mt-3">
            <UButton color="neutral" variant="ghost" size="sm" label="Remover" @click="remover(r.id)" />
          </div>
        </UCard>
      </div>

      <div v-else class="text-center py-16 text-muted">
        <UIcon name="i-lucide-inbox" class="size-8 mx-auto mb-2" />
        <p>{{ view === 'pending' ? 'Nenhuma avaliação aguardando aprovação.' : 'Nada por aqui.' }}</p>
      </div>
    </template>
  </UDashboardPanel>
</template>
