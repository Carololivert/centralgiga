<script setup lang="ts">
import type { Sistema } from '~/types/db'

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
}

function abrir(s: Sistema) {
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
              <div class="min-w-0">
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
