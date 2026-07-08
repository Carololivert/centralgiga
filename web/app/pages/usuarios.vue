<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'

definePageMeta({ middleware: 'role', roles: ['admin'] })

const toast = useToast()

const users = ref<any[]>([])
const carregando = ref(true)
const erro = ref('')

const roleItems = [
  { label: 'Administrador', value: 'admin' },
  { label: 'Supervisor', value: 'supervisor' },
  { label: 'Atendente', value: 'atendente' },
]

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const res = await $fetch<{ users: any[] }>('/api/usuarios')
    users.value = res.users ?? []
  } catch (e: any) {
    erro.value = e?.data?.statusMessage || e?.data?.message || e?.message || 'Erro ao carregar'
  } finally {
    carregando.value = false
  }
}
onMounted(carregar)

async function patch(u: any, body: Record<string, any>) {
  try {
    await $fetch(`/api/usuarios/${u.id}`, { method: 'PATCH', body })
    Object.assign(u, body)
    toast.add({ title: 'Atualizado', color: 'success' })
  } catch (e: any) {
    toast.add({ title: 'Falha ao atualizar', description: e?.data?.statusMessage || e?.message, color: 'error' })
    await carregar()
  }
}

// ── Criar usuário (senha provisória gerada pelo sistema) ──────
const open = ref(false)
const salvando = ref(false)
const novo = reactive({ full_name: '', email: '', role: 'atendente' })

// Senha provisória para exibir uma única vez (após criar ou resetar).
const resultado = ref<{ titulo: string, senha: string } | null>(null)

async function criar() {
  if (!novo.email.trim() || !novo.email.includes('@')) {
    toast.add({ title: 'Informe um e-mail válido.', color: 'warning' })
    return
  }
  salvando.value = true
  try {
    const res = await $fetch<{ senha_provisoria: string }>('/api/usuarios', { method: 'POST', body: { ...novo } })
    open.value = false
    resultado.value = { titulo: `Usuário ${novo.email} criado`, senha: res.senha_provisoria }
    Object.assign(novo, { full_name: '', email: '', role: 'atendente' })
    await carregar()
  } catch (e: any) {
    toast.add({ title: 'Falha ao criar', description: e?.data?.statusMessage || e?.message, color: 'error' })
  } finally {
    salvando.value = false
  }
}

// ── Recuperação (admin) ───────────────────────────────────────
async function resetarSenha(u: any) {
  if (!window.confirm(`Gerar uma nova senha provisória para ${u.email}?`)) return
  try {
    const res = await $fetch<{ senha_provisoria: string }>(`/api/usuarios/${u.id}/reset-senha`, { method: 'POST' })
    u.must_change_password = true
    resultado.value = { titulo: `Nova senha de ${u.email}`, senha: res.senha_provisoria }
  } catch (e: any) {
    toast.add({ title: 'Falha ao resetar senha', description: e?.data?.statusMessage || e?.message, color: 'error' })
  }
}

async function resetar2fa(u: any) {
  if (!window.confirm(`Remover o 2FA de ${u.email}? Ele terá que cadastrar de novo no próximo acesso.`)) return
  try {
    await $fetch(`/api/usuarios/${u.id}/reset-2fa`, { method: 'POST' })
    u.has_2fa = false
    toast.add({ title: '2FA resetado ✓', color: 'success' })
  } catch (e: any) {
    toast.add({ title: 'Falha ao resetar 2FA', description: e?.data?.statusMessage || e?.message, color: 'error' })
  }
}

function acoes(u: any): DropdownMenuItem[][] {
  return [[
    { label: 'Resetar senha', icon: 'i-lucide-key-round', onSelect: () => resetarSenha(u) },
    { label: 'Resetar 2FA', icon: 'i-lucide-shield-off', onSelect: () => resetar2fa(u) },
  ]]
}

async function copiar(txt: string) {
  try {
    await navigator.clipboard.writeText(txt)
    toast.add({ title: 'Copiado ✓', color: 'success' })
  } catch {
    toast.add({ title: 'Não foi possível copiar', color: 'error' })
  }
}

function fmtData(iso: string) {
  return iso ? new Date(iso).toLocaleDateString('pt-BR') : ''
}
</script>

<template>
  <UDashboardPanel id="usuarios">
    <template #header>
      <UDashboardNavbar title="Usuários" icon="i-lucide-users">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton icon="i-lucide-user-plus" label="Novo usuário" @click="open = true" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div>
        <div v-if="carregando" class="flex justify-center py-16 text-muted">
          <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin" />
        </div>

        <UAlert
          v-else-if="erro"
          color="error"
          variant="soft"
          icon="i-lucide-triangle-alert"
          title="Não foi possível carregar os usuários"
          :description="erro"
          :actions="[{ label: 'Tentar de novo', color: 'neutral', variant: 'soft', onClick: carregar }]"
        />

        <template v-else>
          <!-- MOBILE: cartões -->
          <div class="md:hidden space-y-3">
            <div v-for="u in users" :key="u.id" class="rounded-xl border border-default p-4 space-y-3">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <p class="font-medium truncate">{{ u.full_name || '—' }}</p>
                  <p class="text-sm text-muted break-all">{{ u.email }}</p>
                </div>
                <UDropdownMenu :items="acoes(u)">
                  <UButton icon="i-lucide-ellipsis-vertical" color="neutral" variant="ghost" size="sm" />
                </UDropdownMenu>
              </div>
              <div class="flex flex-wrap gap-1">
                <UBadge v-if="u.must_change_password" color="warning" variant="soft" size="sm">Senha provisória</UBadge>
                <UBadge :color="u.has_2fa ? 'success' : 'neutral'" variant="soft" size="sm">
                  {{ u.has_2fa ? '2FA ativo' : 'Sem 2FA' }}
                </UBadge>
              </div>
              <div class="flex items-center justify-between gap-3">
                <USelect
                  :model-value="u.role"
                  :items="roleItems"
                  size="sm"
                  class="flex-1"
                  @update:model-value="(v) => patch(u, { role: v })"
                />
                <div class="flex items-center gap-2 shrink-0">
                  <span class="text-xs text-muted">Ativo</span>
                  <USwitch :model-value="u.active" @update:model-value="(v) => patch(u, { active: v })" />
                </div>
              </div>
            </div>
            <p v-if="!users.length" class="text-center text-muted py-8">Nenhum usuário.</p>
          </div>

          <!-- DESKTOP: tabela -->
          <UCard class="hidden md:block" :ui="{ body: 'p-0 sm:p-0' }">
            <table class="w-full text-sm">
              <thead class="text-left text-muted border-b border-default">
                <tr>
                  <th class="px-4 py-2.5 font-medium">Nome</th>
                  <th class="px-4 py-2.5 font-medium">E-mail</th>
                  <th class="px-4 py-2.5 font-medium">Cargo</th>
                  <th class="px-4 py-2.5 font-medium">Segurança</th>
                  <th class="px-4 py-2.5 font-medium">Ativo</th>
                  <th class="px-4 py-2.5 font-medium">Criado</th>
                  <th class="px-4 py-2.5 font-medium text-right">Ações</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-default">
                <tr v-for="u in users" :key="u.id" class="hover:bg-elevated/50">
                  <td class="px-4 py-2 whitespace-nowrap">{{ u.full_name || '—' }}</td>
                  <td class="px-4 py-2 whitespace-nowrap text-muted">{{ u.email }}</td>
                  <td class="px-4 py-2">
                    <USelect
                      :model-value="u.role"
                      :items="roleItems"
                      size="sm"
                      class="w-40"
                      @update:model-value="(v) => patch(u, { role: v })"
                    />
                  </td>
                  <td class="px-4 py-2">
                    <div class="flex flex-wrap gap-1">
                      <UBadge v-if="u.must_change_password" color="warning" variant="soft" size="sm">Senha provisória</UBadge>
                      <UBadge :color="u.has_2fa ? 'success' : 'neutral'" variant="soft" size="sm">
                        {{ u.has_2fa ? '2FA ativo' : 'Sem 2FA' }}
                      </UBadge>
                    </div>
                  </td>
                  <td class="px-4 py-2">
                    <USwitch :model-value="u.active" @update:model-value="(v) => patch(u, { active: v })" />
                  </td>
                  <td class="px-4 py-2 whitespace-nowrap text-muted">{{ fmtData(u.created_at) }}</td>
                  <td class="px-4 py-2 text-right">
                    <UDropdownMenu :items="acoes(u)">
                      <UButton icon="i-lucide-ellipsis-vertical" color="neutral" variant="ghost" size="sm" />
                    </UDropdownMenu>
                  </td>
                </tr>
                <tr v-if="!users.length">
                  <td colspan="7" class="px-4 py-8 text-center text-muted">Nenhum usuário.</td>
                </tr>
              </tbody>
            </table>
          </UCard>
        </template>

        <!-- Modal: novo usuário -->
        <UModal v-model:open="open" title="Novo usuário">
          <template #body>
            <div class="space-y-4">
              <UFormField label="Nome">
                <UInput v-model="novo.full_name" class="w-full" placeholder="Nome completo" />
              </UFormField>
              <UFormField label="E-mail" required>
                <UInput v-model="novo.email" type="email" class="w-full" placeholder="usuario@giganet.com" />
              </UFormField>
              <UFormField label="Cargo">
                <USelect v-model="novo.role" :items="roleItems" class="w-full" />
              </UFormField>
              <UAlert
                color="info"
                variant="soft"
                icon="i-lucide-info"
                title="Senha provisória automática"
                description="O sistema gera uma senha forte e mostra na tela para você repassar. No primeiro acesso a pessoa cria a própria senha e ativa o 2FA."
              />
              <div class="flex justify-end gap-2 pt-2">
                <UButton color="neutral" variant="ghost" label="Cancelar" @click="open = false" />
                <UButton icon="i-lucide-check" label="Criar" :loading="salvando" @click="criar" />
              </div>
            </div>
          </template>
        </UModal>

        <!-- Modal: senha provisória gerada (exibida uma única vez) -->
        <UModal
          :open="!!resultado"
          title="Senha provisória"
          @update:open="(v: boolean) => { if (!v) resultado = null }"
        >
          <template #body>
            <div v-if="resultado" class="space-y-4">
              <p class="text-sm text-muted">
                {{ resultado.titulo }}. Copie e repasse agora — ela
                <b class="text-default">não será exibida de novo</b>.
              </p>
              <div class="flex items-center gap-2">
                <code class="flex-1 rounded-lg bg-elevated px-3 py-2 font-mono text-lg tracking-wider break-all">
                  {{ resultado.senha }}
                </code>
                <UButton icon="i-lucide-copy" color="neutral" variant="soft" @click="copiar(resultado.senha)" />
              </div>
              <div class="flex justify-end">
                <UButton label="Fechar" color="neutral" variant="ghost" @click="resultado = null" />
              </div>
            </div>
          </template>
        </UModal>
      </div>
    </template>
  </UDashboardPanel>
</template>
