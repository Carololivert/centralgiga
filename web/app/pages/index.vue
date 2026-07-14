<script setup lang="ts">
import type { Job, Sistema } from '~/types/db'

definePageMeta({ middleware: 'role' })

const client = useSupabaseClient()
const { perfil } = usePerfil()

const { data: sistemas } = await useAsyncData('systems', async () => {
  const { data } = await client
    .from('systems')
    .select('*')
    .eq('active', true)
    .order('sort_order')
  return (data ?? []) as Sistema[]
})

// ── Marcador de execução por automação (última execução + tempo ao vivo) ──
// Carrega os jobs recentes e reduz ao ÚLTIMO de cada sistema; o realtime
// mantém o marcador atualizado enquanto uma automação roda.
const { data: jobsRecentes } = await useAsyncData('dashboard-jobs', async () => {
  const { data } = await client
    .from('jobs')
    .select('id, system_slug, status, created_at, started_at, finished_at')
    .order('created_at', { ascending: false })
    .limit(100)
  return (data ?? []) as Job[]
})

const jobPorSistema = ref<Record<string, Job>>({})
function reconstruirMapa() {
  const mapa: Record<string, Job> = {}
  for (const j of jobsRecentes.value ?? []) {
    if (!mapa[j.system_slug]) mapa[j.system_slug] = j // já vem ordenado desc → o 1º é o mais recente
  }
  jobPorSistema.value = mapa
}
reconstruirMapa()

const agora = ref(Date.now())
let ticker: any = null
let canal: any = null
onMounted(() => {
  ticker = setInterval(() => { agora.value = Date.now() }, 1000)
  canal = client
    .channel('dashboard-jobs')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'jobs' }, (payload: any) => {
      const j = payload.new as Job
      if (!j?.system_slug) return
      const atual = jobPorSistema.value[j.system_slug]
      if (!atual || new Date(j.created_at).getTime() >= new Date(atual.created_at).getTime()) {
        jobPorSistema.value = { ...jobPorSistema.value, [j.system_slug]: j }
      }
    })
    .subscribe()
})
onUnmounted(() => {
  if (ticker) clearInterval(ticker)
  if (canal) client.removeChannel(canal)
})

type Marca = { tipo: 'rodando' | 'ok' | 'erro', texto: string }
const marcadores = computed<Record<string, Marca | null>>(() => {
  const out: Record<string, Marca | null> = {}
  for (const s of sistemas.value ?? []) {
    const j = jobPorSistema.value[s.slug]
    if (!j) { out[s.slug] = null; continue }
    if (j.status === 'na_fila' || j.status === 'executando') {
      out[s.slug] = { tipo: 'rodando', texto: cronometro(decorridoJobMs(j, agora.value)) }
    }
    else if (j.status === 'concluido') {
      out[s.slug] = { tipo: 'ok', texto: formatarDuracao(duracaoJobMs(j)) }
    }
    else {
      out[s.slug] = { tipo: 'erro', texto: 'falhou' }
    }
  }
  return out
})

const roleLabel: Record<string, string> = {
  admin: 'Admin',
  supervisor: 'Supervisor',
  atendente: 'Atendente',
}

const iconePorSlug: Record<string, string> = {
  'relatorio-os': 'i-lucide-clipboard-list',
  'termos-agendados': 'i-lucide-file-signature',
  'conferencia-checklist': 'i-lucide-list-checks',
  'giganet-avaliacoes': 'i-lucide-star',
  'verificar-vendas': 'i-lucide-user-check',
  'linhas-canceladas': 'i-lucide-phone-off',
  'remover-linhas': 'i-lucide-trash-2',
  'monitor': 'i-lucide-radio-tower',
}

function abrir(s: Sistema) {
  if (s.kind === 'painel') return navigateTo(`/${s.slug}`)
  if (s.kind === 'inbox' && s.slug === 'giganet-avaliacoes') return navigateTo('/avaliacoes')
  return navigateTo(`/sistema/${s.slug}`)
}
</script>

<template>
  <UDashboardPanel id="inicio">
    <template #header>
      <UDashboardNavbar title="Sistemas" icon="i-lucide-layout-grid">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="space-y-6">
        <div>
          <p class="text-sm text-muted">
            Olá, <strong class="text-default">{{ perfil?.full_name || 'bem-vindo' }}</strong>
          </p>
          <p class="text-muted text-sm">
            Você vê apenas as automações liberadas para o seu cargo.
          </p>
        </div>

        <div
          v-if="sistemas && sistemas.length"
          class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <div
            v-for="s in sistemas"
            :key="s.id"
            class="group flex flex-col rounded-xl border border-default bg-elevated/40 p-5 hover:border-primary/40 hover:shadow-sm transition cursor-pointer"
            @click="abrir(s)"
          >
            <div class="flex items-start gap-3">
              <span class="inline-grid place-items-center size-11 rounded-xl bg-primary/10 text-primary shrink-0">
                <UIcon :name="iconePorSlug[s.slug] || 'i-lucide-cpu'" class="size-5.5" />
              </span>
              <div class="min-w-0 grow">
                <h3 class="font-semibold truncate">{{ s.name }}</h3>
                <div class="flex flex-wrap gap-1 mt-1">
                  <UBadge
                    v-for="r in s.allowed_roles"
                    :key="r"
                    color="neutral"
                    variant="subtle"
                    size="sm"
                    :label="roleLabel[r] || r"
                  />
                  <UBadge
                    v-if="s.kind === 'inbox'"
                    color="primary"
                    variant="soft"
                    size="sm"
                    label="aprovação"
                  />
                </div>
              </div>

              <!-- marcador de execução: rodando (tempo ao vivo) / última duração / falhou -->
              <div v-if="marcadores[s.slug]" class="shrink-0" @click.stop>
                <span
                  v-if="marcadores[s.slug]!.tipo === 'rodando'"
                  class="inline-flex items-center gap-1 rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium tabular-nums"
                  title="Executando agora"
                >
                  <UIcon name="i-lucide-loader-circle" class="size-3.5 animate-spin" />{{ marcadores[s.slug]!.texto }}
                </span>
                <span
                  v-else-if="marcadores[s.slug]!.tipo === 'ok'"
                  class="inline-flex items-center gap-1 rounded-full bg-elevated text-muted px-2 py-0.5 text-xs tabular-nums"
                  title="Tempo da última execução"
                >
                  <UIcon name="i-lucide-timer" class="size-3.5" />{{ marcadores[s.slug]!.texto || 'ok' }}
                </span>
                <span
                  v-else
                  class="inline-flex items-center gap-1 rounded-full bg-error/10 text-error px-2 py-0.5 text-xs"
                  title="Última execução falhou"
                >
                  <UIcon name="i-lucide-circle-x" class="size-3.5" />falhou
                </span>
              </div>
            </div>

            <p class="text-sm text-muted mt-3 grow">{{ s.description }}</p>

            <div class="mt-4 flex items-center gap-1 text-sm font-medium text-primary">
              <span>{{ s.kind === 'inbox' ? 'Abrir caixa' : 'Abrir' }}</span>
              <UIcon
                name="i-lucide-arrow-right"
                class="size-4 group-hover:translate-x-0.5 transition-transform"
              />
            </div>
          </div>
        </div>

        <div v-else class="text-center py-16 text-muted">
          <UIcon name="i-lucide-inbox" class="size-8 mx-auto mb-2" />
          <p>Nenhum sistema liberado para o seu cargo ainda.</p>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
