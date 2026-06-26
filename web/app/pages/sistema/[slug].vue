<script setup lang="ts">
import type { Job, JobLog, Sistema } from '~/types/db'

definePageMeta({ middleware: 'role' })

const route = useRoute()
const client = useSupabaseClient()
const user = useSupabaseUser()
const toast = useToast()

const slug = computed(() => String(route.params.slug))
const ehChecklist = computed(() => slug.value === 'conferencia-checklist')
const ehDestrutivo = computed(() => slug.value === 'remover-linhas')

const { data: sistema } = await useAsyncData(
  () => `system-${slug.value}`,
  async () => {
    const { data } = await client
      .from('systems')
      .select('*')
      .eq('slug', slug.value)
      .maybeSingle()
    return data as Sistema | null
  },
)

const iconePorSlug: Record<string, string> = {
  'relatorio-os': 'i-lucide-clipboard-list',
  'termos-agendados': 'i-lucide-file-signature',
  'conferencia-checklist': 'i-lucide-list-checks',
  'verificar-vendas': 'i-lucide-user-check',
  'linhas-canceladas': 'i-lucide-phone-off',
  'remover-linhas': 'i-lucide-trash-2',
}

// ── parâmetros (param_schema) ──────────────────────────────────
const campos = computed(() =>
  Object.entries(sistema.value?.param_schema ?? {}).map(([key, def]) => ({
    key,
    ...(def as any),
  })),
)
const paramsModel = reactive<Record<string, any>>({})
watchEffect(() => {
  for (const c of campos.value) {
    if (!(c.key in paramsModel)) paramsModel[c.key] = c.default ?? ''
  }
})

// ── execução atual ─────────────────────────────────────────────
const jobAtual = ref<Job | null>(null)
const logs = ref<JobLog[]>([])
const enviando = ref(false)
const mostrarLogs = ref(false)
let canal: any = null

const emAndamento = computed(
  () => jobAtual.value?.status === 'na_fila' || jobAtual.value?.status === 'executando',
)
const logsTexto = computed(() => logs.value.map(l => l.line).join('\n'))

const statusInfo: Record<string, { label: string, color: any, icon: string }> = {
  na_fila: { label: 'Na fila', color: 'neutral', icon: 'i-lucide-clock' },
  executando: { label: 'Executando', color: 'info', icon: 'i-lucide-loader-circle' },
  concluido: { label: 'Concluído', color: 'success', icon: 'i-lucide-check' },
  erro: { label: 'Erro', color: 'error', icon: 'i-lucide-x' },
}

function parseDados(j: Job | null): any | null {
  if (!j || !ehChecklist.value || !j.result_preview) return null
  try {
    return JSON.parse(j.result_preview)
  } catch {
    return null
  }
}
const dadosAtual = computed(() => parseDados(jobAtual.value))

// ── histórico ──────────────────────────────────────────────────
const { data: historico, refresh: refreshHistorico } = await useAsyncData(
  () => `jobs-${slug.value}`,
  async () => {
    const { data } = await client
      .from('jobs')
      .select('*')
      .eq('system_slug', slug.value)
      .order('created_at', { ascending: false })
      .limit(20)
    return (data ?? []) as Job[]
  },
)
const abertoId = ref<string | null>(null)

function inscrever(jobId: string) {
  if (canal) client.removeChannel(canal)
  canal = client
    .channel(`job-${jobId}`)
    .on(
      'postgres_changes',
      { event: '*', schema: 'public', table: 'jobs', filter: `id=eq.${jobId}` },
      (payload: any) => {
        jobAtual.value = payload.new as Job
        if (['concluido', 'erro'].includes(payload.new.status)) refreshHistorico()
      },
    )
    .on(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'job_logs', filter: `job_id=eq.${jobId}` },
      (payload: any) => {
        logs.value.push(payload.new as JobLog)
      },
    )
    .subscribe()
}

async function executar() {
  if (!user.value || enviando.value) return
  for (const c of campos.value) {
    if (c.required && !paramsModel[c.key]) {
      toast.add({ title: `Preencha "${c.label || c.key}"`, color: 'warning' })
      return
    }
  }

  // confirmação extra para a remoção REAL (fora da simulação)
  if (ehDestrutivo.value && paramsModel.dry_run === false) {
    if (!window.confirm('ATENÇÃO: isto vai REMOVER linhas no SGP DE VERDADE (não é simulação). Tem certeza?')) {
      return
    }
  }

  enviando.value = true
  logs.value = []
  jobAtual.value = null
  mostrarLogs.value = false

  const { data, error } = await client
    .from('jobs')
    .insert({
      system_slug: slug.value,
      requested_by: user.value.id,
      params: { ...paramsModel },
      status: 'na_fila',
    })
    .select()
    .single()

  enviando.value = false

  if (error) {
    toast.add({ title: 'Não foi possível executar', description: error.message, color: 'error' })
    return
  }

  jobAtual.value = data as Job
  inscrever((data as Job).id)
  refreshHistorico()
}

function copiar(texto: string | null | undefined) {
  if (!texto) return
  navigator.clipboard.writeText(texto)
  toast.add({ title: 'Copiado para a área de transferência', color: 'success' })
}

async function baixar(path: string | null) {
  if (!path) return
  const { data, error } = await client.storage.from('resultados').createSignedUrl(path, 60)
  if (error || !data) {
    toast.add({ title: 'Falha ao gerar o link', description: error?.message, color: 'error' })
    return
  }
  window.open(data.signedUrl, '_blank')
}

function fmtData(iso: string) {
  return new Date(iso).toLocaleString('pt-BR')
}

onUnmounted(() => {
  if (canal) client.removeChannel(canal)
})
</script>

<template>
  <UDashboardPanel id="sistema">
    <template #header>
      <UDashboardNavbar
        :title="sistema?.name || 'Sistema'"
        :icon="iconePorSlug[slug] || 'i-lucide-cpu'"
      >
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <template v-if="sistema">
        <p class="text-sm text-muted mb-5">{{ sistema.description }}</p>

        <!-- Executar -->
        <UCard class="mb-6">
          <div class="flex flex-col gap-4">
            <UAlert
              v-if="ehDestrutivo"
              color="warning"
              variant="soft"
              icon="i-lucide-alert-triangle"
              title="Ação destrutiva"
              description="Por padrão roda em simulação (não remove). Desmarque 'Apenas simular' só quando tiver certeza — toda execução fica registrada na auditoria."
            />

            <div v-if="campos.length" class="grid gap-4 sm:grid-cols-2">
              <template v-for="c in campos" :key="c.key">
                <div v-if="c.type === 'boolean'" class="flex items-center gap-3 sm:col-span-2">
                  <USwitch v-model="paramsModel[c.key]" />
                  <span class="text-sm">{{ c.label || c.key }}</span>
                </div>
                <UFormField v-else :label="c.label || c.key" :required="c.required">
                  <USelect
                    v-if="c.type === 'select'"
                    v-model="paramsModel[c.key]"
                    :items="c.options"
                    class="w-full"
                  />
                  <UInput v-else v-model="paramsModel[c.key]" class="w-full" />
                </UFormField>
              </template>
            </div>

            <div class="flex items-center gap-3">
              <UButton
                icon="i-lucide-play"
                size="lg"
                label="Executar"
                :loading="enviando"
                :disabled="emAndamento"
                @click="executar"
              />
              <UBadge
                v-if="jobAtual"
                :color="statusInfo[jobAtual.status].color"
                variant="subtle"
                :icon="statusInfo[jobAtual.status].icon"
                :label="statusInfo[jobAtual.status].label"
              />
            </div>
          </div>
        </UCard>

        <!-- Resultado / execução -->
        <UCard v-if="jobAtual" class="mb-6">
          <template #header>
            <div class="flex items-center justify-between gap-2">
              <h3 class="font-semibold">
                {{ jobAtual.status === 'concluido' ? 'Resultado' : 'Execução' }}
              </h3>
              <div v-if="jobAtual.status === 'concluido'" class="flex items-center gap-2">
                <UButton
                  v-if="!ehChecklist"
                  icon="i-lucide-copy"
                  size="sm"
                  label="Copiar"
                  @click="copiar(jobAtual.result_preview)"
                />
                <UButton
                  v-if="jobAtual.result_path"
                  icon="i-lucide-download"
                  size="sm"
                  color="neutral"
                  variant="ghost"
                  :label="ehChecklist ? 'Baixar .json' : 'Baixar .txt'"
                  @click="baixar(jobAtual.result_path)"
                />
              </div>
            </div>
          </template>

          <UAlert
            v-if="jobAtual.status === 'erro'"
            color="error"
            variant="soft"
            icon="i-lucide-triangle-alert"
            title="Falhou"
            :description="jobAtual.error || 'erro desconhecido'"
          />

          <template v-else-if="emAndamento">
            <p v-if="jobAtual.status === 'na_fila'" class="text-sm text-muted mb-2">
              <UIcon name="i-lucide-loader-circle" class="animate-spin size-4 align-[-2px]" />
              aguardando o worker pegar o job…
            </p>
            <pre
              v-if="logs.length"
              class="text-xs font-mono bg-muted rounded-lg p-3 max-h-80 overflow-auto whitespace-pre-wrap"
            >{{ logsTexto }}</pre>
            <p v-else class="text-sm text-muted">iniciando…</p>
          </template>

          <template v-else-if="jobAtual.status === 'concluido'">
            <ChecklistResultado v-if="dadosAtual" :dados="dadosAtual" />
            <pre
              v-else
              class="text-xs sm:text-sm font-mono bg-muted rounded-lg p-4 max-h-[34rem] overflow-auto whitespace-pre-wrap leading-relaxed"
            >{{ jobAtual.result_preview }}</pre>

            <div v-if="logs.length" class="mt-3">
              <UButton
                :icon="mostrarLogs ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                color="neutral"
                variant="link"
                size="xs"
                :label="mostrarLogs ? 'ocultar logs' : 'ver logs da execução'"
                class="px-0"
                @click="mostrarLogs = !mostrarLogs"
              />
              <pre
                v-if="mostrarLogs"
                class="text-xs font-mono bg-muted rounded-lg p-3 max-h-72 overflow-auto whitespace-pre-wrap mt-1"
              >{{ logsTexto }}</pre>
            </div>
          </template>
        </UCard>

        <!-- Histórico -->
        <UCard>
          <template #header>
            <h3 class="font-semibold">Histórico</h3>
          </template>
          <div v-if="historico && historico.length" class="divide-y divide-default">
            <div v-for="j in historico" :key="j.id" class="py-2.5">
              <div class="flex items-center gap-3">
                <UBadge
                  :color="statusInfo[j.status].color"
                  variant="subtle"
                  size="sm"
                  :icon="statusInfo[j.status].icon"
                  :label="statusInfo[j.status].label"
                />
                <span class="text-sm text-muted">{{ fmtData(j.created_at) }}</span>
                <span class="ml-auto" />
                <UButton
                  v-if="j.status === 'concluido' && j.result_preview"
                  :icon="abertoId === j.id ? 'i-lucide-chevron-down' : 'i-lucide-eye'"
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  :label="abertoId === j.id ? 'fechar' : 'ver'"
                  @click="abertoId = abertoId === j.id ? null : j.id"
                />
                <UButton
                  v-if="j.status === 'concluido' && j.result_preview && !ehChecklist"
                  icon="i-lucide-copy"
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  @click="copiar(j.result_preview)"
                />
              </div>

              <template v-if="abertoId === j.id">
                <ChecklistResultado v-if="parseDados(j)" :dados="parseDados(j)" class="mt-2" />
                <pre
                  v-else
                  class="text-xs font-mono bg-muted rounded-lg p-3 max-h-96 overflow-auto whitespace-pre-wrap mt-2"
                >{{ j.result_preview }}</pre>
              </template>

              <p v-if="j.status === 'erro'" class="text-xs text-error mt-1 truncate">
                {{ j.error }}
              </p>
            </div>
          </div>
          <p v-else class="text-sm text-muted">Nenhuma execução ainda.</p>
        </UCard>
      </template>

      <div v-else class="text-center py-16 text-muted">
        <UIcon name="i-lucide-lock" class="size-8 mx-auto mb-2" />
        <p>Sistema não encontrado ou sem acesso para o seu cargo.</p>
      </div>
    </template>
  </UDashboardPanel>
</template>
