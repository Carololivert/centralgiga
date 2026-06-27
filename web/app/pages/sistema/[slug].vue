<script setup lang="ts">
import type { Job, JobLog, Sistema } from '~/types/db'

definePageMeta({ middleware: 'role' })

const route = useRoute()
const client = useSupabaseClient()
const user = useSupabaseUser()
const toast = useToast()
const { isAdmin } = usePerfil()

const slug = computed(() => String(route.params.slug))
const ehChecklist = computed(() => slug.value === 'conferencia-checklist')
const ehDestrutivo = computed(() => slug.value === 'remover-linhas')

const { data: sistema } = await useAsyncData(
  () => `system-${slug.value}`,
  async () => {
    const { data } = await client.from('systems').select('*').eq('slug', slug.value).maybeSingle()
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

const campos = computed(() =>
  Object.entries(sistema.value?.param_schema ?? {}).map(([key, def]) => ({ key, ...(def as any) })),
)
const paramsModel = reactive<Record<string, any>>({})
watchEffect(() => {
  for (const c of campos.value) if (!(c.key in paramsModel)) paramsModel[c.key] = c.default ?? ''
})

const jobAtual = ref<Job | null>(null)
const logs = ref<JobLog[]>([])
const enviando = ref(false)
const mostrarLogs = ref(false)
let canal: any = null

const emAndamento = computed(
  () => jobAtual.value?.status === 'na_fila' || jobAtual.value?.status === 'executando',
)
const concluido = computed(() => jobAtual.value?.status === 'concluido')
const logsTexto = computed(() => logs.value.map(l => l.line).join('\n'))

const statusInfo: Record<string, { label: string, color: any, icon: string }> = {
  na_fila: { label: 'Na fila', color: 'neutral', icon: 'i-lucide-clock' },
  executando: { label: 'Processando', color: 'info', icon: 'i-lucide-loader-circle' },
  concluido: { label: 'Concluído', color: 'success', icon: 'i-lucide-circle-check' },
  erro: { label: 'Falhou', color: 'error', icon: 'i-lucide-circle-x' },
}

function parseDados(j: Job | null): any | null {
  if (!j || !ehChecklist.value || !j.result_preview) return null
  try { return JSON.parse(j.result_preview) } catch { return null }
}
const dadosAtual = computed(() => parseDados(jobAtual.value))

const { data: historico, refresh: refreshHistorico } = await useAsyncData(
  () => `jobs-${slug.value}`,
  async () => {
    const { data } = await client.from('jobs').select('*').eq('system_slug', slug.value)
      .order('created_at', { ascending: false }).limit(20)
    return (data ?? []) as Job[]
  },
)
const abertoId = ref<string | null>(null)

function inscrever(jobId: string) {
  if (canal) client.removeChannel(canal)
  canal = client
    .channel(`job-${jobId}`)
    .on('postgres_changes', { event: '*', schema: 'public', table: 'jobs', filter: `id=eq.${jobId}` },
      (payload: any) => {
        jobAtual.value = payload.new as Job
        if (['concluido', 'erro'].includes(payload.new.status)) refreshHistorico()
      })
    .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'job_logs', filter: `job_id=eq.${jobId}` },
      (payload: any) => { logs.value.push(payload.new as JobLog) })
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
  if (ehDestrutivo.value && paramsModel.dry_run === false) {
    if (!window.confirm('ATENÇÃO: isto vai REMOVER linhas no SGP DE VERDADE (não é simulação). Tem certeza?')) return
  }

  enviando.value = true
  logs.value = []
  jobAtual.value = null
  mostrarLogs.value = false

  const { data, error } = await client.from('jobs')
    .insert({ system_slug: slug.value, requested_by: user.value.id, params: { ...paramsModel }, status: 'na_fila' })
    .select().single()
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
  toast.add({ title: 'Copiado!', color: 'success' })
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

onUnmounted(() => { if (canal) client.removeChannel(canal) })
</script>

<template>
  <UDashboardPanel id="sistema">
    <template #header>
      <UDashboardNavbar :title="sistema?.name || 'Sistema'" :icon="iconePorSlug[slug] || 'i-lucide-cpu'">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <!-- wrapper único: evita que os cards virem "flex items" do body e se espremam -->
      <div v-if="sistema" class="space-y-6">
        <p class="text-sm text-muted">{{ sistema.description }}</p>

        <!-- Executar -->
        <UCard>
          <div class="flex flex-col gap-4">
            <UAlert
              v-if="ehDestrutivo"
              color="warning"
              variant="soft"
              icon="i-lucide-alert-triangle"
              title="Ação que altera o SGP"
              description="Por segurança vem marcado como simulação (não remove nada). Só desmarque 'Apenas simular' quando tiver certeza."
            />

            <div v-if="campos.length" class="grid gap-4 sm:grid-cols-2">
              <template v-for="c in campos" :key="c.key">
                <div v-if="c.type === 'boolean'" class="flex items-center gap-3 sm:col-span-2">
                  <USwitch v-model="paramsModel[c.key]" />
                  <span class="text-sm">{{ c.label || c.key }}</span>
                </div>
                <UFormField v-else :label="c.label || c.key" :required="c.required">
                  <USelect v-if="c.type === 'select'" v-model="paramsModel[c.key]" :items="c.options" class="w-full" />
                  <UInput v-else v-model="paramsModel[c.key]" class="w-full" />
                </UFormField>
              </template>
            </div>

            <div>
              <UButton
                icon="i-lucide-play"
                size="lg"
                label="Executar"
                :loading="enviando"
                :disabled="emAndamento"
                @click="executar"
              />
            </div>
          </div>
        </UCard>

        <!-- Resultado / execução (amigável) -->
        <UCard v-if="jobAtual">
          <template #header>
            <div class="flex items-center justify-between gap-2 flex-wrap">
              <UBadge
                :color="statusInfo[jobAtual.status].color"
                variant="subtle"
                :icon="statusInfo[jobAtual.status].icon"
                :label="statusInfo[jobAtual.status].label"
              />
              <div v-if="concluido" class="flex items-center gap-2">
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
                  :label="ehChecklist ? 'Baixar planilha' : 'Baixar'"
                  @click="baixar(jobAtual.result_path)"
                />
              </div>
            </div>
          </template>

          <div v-if="jobAtual.status === 'erro'" class="text-center py-8">
            <UIcon name="i-lucide-circle-x" class="size-10 mx-auto text-error mb-3" />
            <p class="font-medium">Não foi possível concluir desta vez.</p>
            <p class="text-sm text-muted mt-1">Tente executar de novo. Se continuar, avise o administrador.</p>
          </div>

          <div v-else-if="emAndamento" class="text-center py-10">
            <UIcon name="i-lucide-loader-circle" class="size-10 mx-auto text-primary animate-spin mb-3" />
            <p class="font-medium">
              {{ jobAtual.status === 'na_fila' ? 'Na fila, começando já já…' : 'Processando, aguarde…' }}
            </p>
            <p class="text-sm text-muted mt-1">Isso pode levar de alguns segundos a uns minutos.</p>
          </div>

          <template v-else-if="concluido">
            <ChecklistResultado v-if="dadosAtual" :dados="dadosAtual" />
            <div v-else>
              <p class="text-sm text-muted mb-2">Resultado pronto — copie e cole onde precisar:</p>
              <pre class="text-sm whitespace-pre-wrap break-words leading-relaxed rounded-lg border border-default bg-elevated/40 p-4 max-h-[34rem] overflow-auto font-sans">{{ jobAtual.result_preview }}</pre>
            </div>
          </template>

          <div v-if="isAdmin && logs.length" class="mt-3">
            <UButton
              :icon="mostrarLogs ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
              color="neutral"
              variant="link"
              size="xs"
              :label="mostrarLogs ? 'ocultar detalhes técnicos' : 'ver detalhes técnicos'"
              class="px-0"
              @click="mostrarLogs = !mostrarLogs"
            />
            <pre v-if="mostrarLogs" class="text-xs font-mono bg-muted rounded-lg p-3 max-h-72 overflow-auto whitespace-pre-wrap break-words mt-1">{{ logsTexto }}</pre>
          </div>
        </UCard>

        <!-- Histórico -->
        <UCard>
          <template #header>
            <h3 class="font-semibold">Histórico</h3>
          </template>
          <div v-if="historico && historico.length" class="divide-y divide-default">
            <div v-for="j in historico" :key="j.id" class="py-2.5">
              <div class="flex items-center gap-2 sm:gap-3 flex-wrap">
                <UBadge
                  :color="statusInfo[j.status].color"
                  variant="subtle"
                  size="sm"
                  :icon="statusInfo[j.status].icon"
                  :label="statusInfo[j.status].label"
                />
                <span class="text-xs sm:text-sm text-muted">{{ fmtData(j.created_at) }}</span>
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
                <pre v-else class="text-sm whitespace-pre-wrap break-words leading-relaxed rounded-lg border border-default bg-elevated/40 p-4 max-h-96 overflow-auto font-sans mt-2">{{ j.result_preview }}</pre>
              </template>

              <p v-if="j.status === 'erro'" class="text-xs text-muted mt-1">Não concluiu — tente de novo.</p>
            </div>
          </div>
          <p v-else class="text-sm text-muted">Nenhuma execução ainda.</p>
        </UCard>
      </div>

      <div v-else class="text-center py-16 text-muted">
        <UIcon name="i-lucide-lock" class="size-8 mx-auto mb-2" />
        <p>Sistema não encontrado ou sem acesso para o seu cargo.</p>
      </div>
    </template>
  </UDashboardPanel>
</template>
