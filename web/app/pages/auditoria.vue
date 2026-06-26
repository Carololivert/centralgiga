<script setup lang="ts">
import type { AuditEntry } from '~/types/db'

definePageMeta({ middleware: 'role', roles: ['admin'] })

const client = useSupabaseClient()

const { data } = await useAsyncData('auditoria', async () => {
  const [{ data: logs }, { data: perfis }] = await Promise.all([
    client.from('audit_log').select('*').order('created_at', { ascending: false }).limit(100),
    client.from('profiles').select('id, full_name'),
  ])
  const nomes = new Map((perfis ?? []).map((p: any) => [p.id, p.full_name]))
  return ((logs ?? []) as AuditEntry[]).map(l => ({
    ...l,
    nome: l.user_id ? (nomes.get(l.user_id) || '—') : 'sistema',
  }))
})

const rotuloAcao: Record<string, string> = {
  'remover-linhas': 'Remover linhas',
  'avaliacao-aprovada': 'Avaliação aprovada',
  'avaliacao-rejeitada': 'Avaliação rejeitada',
}

function fmtData(iso: string) {
  return new Date(iso).toLocaleString('pt-BR')
}
function resumoDetalhe(d: Record<string, any>) {
  if (!d) return ''
  if (d.resumo) return String(d.resumo).split('\n')[0]
  const partes = Object.entries(d)
    .filter(([k]) => k !== 'resumo')
    .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`)
  return partes.join(' · ')
}
</script>

<template>
  <UDashboardPanel id="auditoria">
    <template #header>
      <UDashboardNavbar title="Auditoria" icon="i-lucide-scroll-text">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UCard v-if="data && data.length" :ui="{ body: 'p-0 sm:p-0' }">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="text-left text-muted border-b border-default">
              <tr>
                <th class="px-4 py-2.5 font-medium">Data/hora</th>
                <th class="px-4 py-2.5 font-medium">Usuário</th>
                <th class="px-4 py-2.5 font-medium">Ação</th>
                <th class="px-4 py-2.5 font-medium">Detalhe</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-default">
              <tr v-for="l in data" :key="l.id" class="hover:bg-elevated/50">
                <td class="px-4 py-2.5 whitespace-nowrap text-muted">{{ fmtData(l.created_at) }}</td>
                <td class="px-4 py-2.5 whitespace-nowrap">{{ l.nome }}</td>
                <td class="px-4 py-2.5">
                  <UBadge color="neutral" variant="subtle" size="sm" :label="rotuloAcao[l.action] || l.action" />
                </td>
                <td class="px-4 py-2.5 text-muted truncate max-w-md">{{ resumoDetalhe(l.detail) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </UCard>

      <div v-else class="text-center py-16 text-muted">
        <UIcon name="i-lucide-scroll-text" class="size-8 mx-auto mb-2" />
        <p>Nenhuma ação registrada ainda.</p>
      </div>
    </template>
  </UDashboardPanel>
</template>
