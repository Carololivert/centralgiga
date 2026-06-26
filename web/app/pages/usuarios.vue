<script setup lang="ts">
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
onMounted(carregar) // client-only: o cookie de sessão é enviado normalmente

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

// criar
const open = ref(false)
const salvando = ref(false)
const novo = reactive({ full_name: '', email: '', password: '', role: 'atendente' })

async function criar() {
  if (!novo.email.trim() || novo.password.length < 6) {
    toast.add({ title: 'Informe e-mail e senha (mín. 6).', color: 'warning' })
    return
  }
  salvando.value = true
  try {
    await $fetch('/api/usuarios', { method: 'POST', body: { ...novo } })
    toast.add({ title: 'Usuário criado ✓', color: 'success' })
    open.value = false
    Object.assign(novo, { full_name: '', email: '', password: '', role: 'atendente' })
    await carregar()
  } catch (e: any) {
    toast.add({ title: 'Falha ao criar', description: e?.data?.statusMessage || e?.message, color: 'error' })
  } finally {
    salvando.value = false
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

      <UCard v-else :ui="{ body: 'p-0 sm:p-0' }">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="text-left text-muted border-b border-default">
              <tr>
                <th class="px-4 py-2.5 font-medium">Nome</th>
                <th class="px-4 py-2.5 font-medium">E-mail</th>
                <th class="px-4 py-2.5 font-medium">Cargo</th>
                <th class="px-4 py-2.5 font-medium">Ativo</th>
                <th class="px-4 py-2.5 font-medium">Criado</th>
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
                  <USwitch
                    :model-value="u.active"
                    @update:model-value="(v) => patch(u, { active: v })"
                  />
                </td>
                <td class="px-4 py-2 whitespace-nowrap text-muted">{{ fmtData(u.created_at) }}</td>
              </tr>
              <tr v-if="!users.length">
                <td colspan="5" class="px-4 py-8 text-center text-muted">Nenhum usuário.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </UCard>

      <UModal v-model:open="open" title="Novo usuário">
      <template #body>
        <div class="space-y-4">
          <UFormField label="Nome">
            <UInput v-model="novo.full_name" class="w-full" placeholder="Nome completo" />
          </UFormField>
          <UFormField label="E-mail" required>
            <UInput v-model="novo.email" type="email" class="w-full" placeholder="usuario@giganet.com" />
          </UFormField>
          <UFormField label="Senha" required>
            <UInput v-model="novo.password" type="password" class="w-full" placeholder="mín. 6 caracteres" />
          </UFormField>
          <UFormField label="Cargo">
            <USelect v-model="novo.role" :items="roleItems" class="w-full" />
          </UFormField>
          <div class="flex justify-end gap-2 pt-2">
            <UButton color="neutral" variant="ghost" label="Cancelar" @click="open = false" />
            <UButton icon="i-lucide-check" label="Criar" :loading="salvando" @click="criar" />
          </div>
        </div>
      </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
