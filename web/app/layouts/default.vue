<script setup lang="ts">
import type { NavigationMenuItem, DropdownMenuItem } from '@nuxt/ui'
import type { Sistema } from '~/types/db'

const { perfil, isAdmin, carregar } = usePerfil()
const client = useSupabaseClient()
const colorMode = useColorMode()
await carregar()

// sistemas do cargo (RLS filtra) para o menu lateral
const { data: sistemas } = await useAsyncData('nav-systems', async () => {
  const { data } = await client
    .from('systems')
    .select('slug, name, kind, sort_order, active')
    .eq('active', true)
    .order('sort_order')
  return (data ?? []) as Sistema[]
})

const iconePorSlug: Record<string, string> = {
  'relatorio-os': 'i-lucide-clipboard-list',
  'termos-agendados': 'i-lucide-file-signature',
  'conferencia-checklist': 'i-lucide-list-checks',
  'giganet-avaliacoes': 'i-lucide-star',
  'verificar-vendas': 'i-lucide-user-check',
  'linhas-canceladas': 'i-lucide-phone-off',
  'remover-linhas': 'i-lucide-trash-2',
}

const links = computed<NavigationMenuItem[][]>(() => {
  const grupos: NavigationMenuItem[][] = [
    [
      { label: 'Painel', type: 'label' as const },
      { label: 'Início', icon: 'i-lucide-home', to: '/' },
    ],
  ]

  const sis = (sistemas.value ?? []).map(s => ({
    label: s.name,
    icon: iconePorSlug[s.slug] || 'i-lucide-cpu',
    to: s.kind === 'inbox' && s.slug === 'giganet-avaliacoes' ? '/avaliacoes' : `/sistema/${s.slug}`,
  }))
  if (sis.length) {
    grupos.push([{ label: 'Sistemas', type: 'label' as const }, ...sis])
  }

  if (isAdmin.value) {
    grupos.push([
      { label: 'Administração', type: 'label' as const },
      { label: 'Usuários', icon: 'i-lucide-users', to: '/usuarios' },
      { label: 'Auditoria', icon: 'i-lucide-scroll-text', to: '/auditoria' },
    ])
  }
  return grupos
})

const roleLabel = computed(
  () =>
    ({ admin: 'Administrador', supervisor: 'Supervisor', atendente: 'Atendente' })[
      perfil.value?.role ?? 'atendente'
    ],
)

function iniciais(nome?: string | null) {
  if (!nome) return '?'
  const p = nome.trim().split(/\s+/)
  return ((p[0]?.[0] ?? '') + (p.length > 1 ? p[p.length - 1]![0] : '')).toUpperCase()
}

async function sair() {
  await client.auth.signOut()
  await navigateTo('/login')
}

const userMenu = computed<DropdownMenuItem[][]>(() => [
  [{ label: perfil.value?.full_name || 'Conta', type: 'label' as const }],
  [{
    label: 'Segurança',
    icon: 'i-lucide-shield-check',
    onSelect: () => { navigateTo('/conta/seguranca') },
  }, {
    label: colorMode.value === 'dark' ? 'Tema claro' : 'Tema escuro',
    icon: colorMode.value === 'dark' ? 'i-lucide-sun' : 'i-lucide-moon',
    onSelect: () => { colorMode.preference = colorMode.value === 'dark' ? 'light' : 'dark' },
  }],
  [{ label: 'Sair', icon: 'i-lucide-log-out', color: 'error' as const, onSelect: sair }],
])
</script>

<template>
  <UDashboardGroup>
    <UDashboardSidebar
      collapsible
      resizable
      :default-size="20"
      :min-size="16"
      :max-size="28"
      :ui="{ header: 'h-auto py-3', footer: 'border-t border-default p-2' }"
    >
      <template #header="{ collapsed }">
        <AppLogo :collapsed="collapsed" />
      </template>

      <template #default="{ collapsed }">
        <UNavigationMenu
          :collapsed="collapsed"
          :items="links"
          orientation="vertical"
          highlight
          :ui="{ link: 'py-2', label: 'text-[11px] uppercase tracking-wider text-muted' }"
        />
      </template>

      <template #footer="{ collapsed }">
        <UDropdownMenu
          :items="userMenu"
          :content="{ align: 'start', side: 'top' }"
          class="w-full"
        >
          <button
            type="button"
            class="w-full flex items-center gap-3 rounded-lg p-2 text-left hover:bg-elevated transition-colors"
            :class="collapsed ? 'justify-center' : ''"
          >
            <UAvatar :text="iniciais(perfil?.full_name)" :alt="perfil?.full_name || 'Conta'" size="md" />
            <template v-if="!collapsed">
              <span class="flex flex-col min-w-0 flex-1 leading-tight">
                <span class="text-sm font-medium truncate">{{ perfil?.full_name || 'Conta' }}</span>
                <span class="text-xs text-muted">{{ roleLabel }}</span>
              </span>
              <UIcon name="i-lucide-chevrons-up-down" class="size-4 text-muted shrink-0" />
            </template>
          </button>
        </UDropdownMenu>
      </template>
    </UDashboardSidebar>

    <slot />
  </UDashboardGroup>
</template>
