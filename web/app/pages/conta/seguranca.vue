<script setup lang="ts">
definePageMeta({ middleware: 'role' })

const supabase = useSupabaseClient()
const toast = useToast()

// ── Status do 2FA ─────────────────────────────────────────────
const tem2fa = ref<boolean | null>(null)

async function carregarStatus2fa() {
  const { data } = await supabase.auth.mfa.listFactors()
  tem2fa.value = (data?.totp || []).some(f => f.status === 'verified')
}
onMounted(carregarStatus2fa)

async function reconfigurar2fa() {
  const ok = window.confirm(
    'Isto vai remover o 2FA atual. Você será desconectado e, ao entrar de novo, cadastrará um novo autenticador. Continuar?',
  )
  if (!ok) return
  const { data } = await supabase.auth.mfa.listFactors()
  for (const f of (data?.all || [])) {
    await supabase.auth.mfa.unenroll({ factorId: f.id })
  }
  // Sair força um novo login: a sessão é reavaliada do zero (sem AAL em
  // cache), e o porteiro leva direto para cadastrar o novo 2FA.
  await supabase.auth.signOut()
  toast.add({ title: '2FA removido. Entre de novo para cadastrar o novo.', color: 'info', icon: 'i-lucide-info' })
  await navigateTo('/login')
}

// ── Trocar senha ──────────────────────────────────────────────
const senhaAtual = ref('')
const senha = ref('')
const confirmacao = ref('')
const salvando = ref(false)

const regras = computed(() => regrasSenha(senha.value))
const coincide = computed(() => confirmacao.value.length > 0 && senha.value === confirmacao.value)
const podeSalvar = computed(() => !!senhaAtual.value && senhaValida(senha.value) && coincide.value)

async function trocarSenha() {
  if (!podeSalvar.value) return
  salvando.value = true
  try {
    await $fetch('/api/conta/senha', {
      method: 'POST',
      body: { senha: senha.value, senha_atual: senhaAtual.value },
    })
    toast.add({ title: 'Senha atualizada ✓', color: 'success', icon: 'i-lucide-check' })
    senhaAtual.value = ''
    senha.value = ''
    confirmacao.value = ''
  } catch (e: any) {
    toast.add({
      title: 'Não foi possível trocar a senha',
      description: e?.data?.statusMessage || e?.message,
      color: 'error',
      icon: 'i-lucide-triangle-alert',
    })
  } finally {
    salvando.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="seguranca">
    <template #header>
      <UDashboardNavbar title="Segurança da conta" icon="i-lucide-shield-check">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="max-w-xl space-y-6">
        <!-- 2FA -->
        <UCard>
          <div class="flex items-start justify-between gap-4">
            <div>
              <h2 class="font-semibold flex items-center gap-2">
                <UIcon name="i-lucide-smartphone" class="size-5" />
                Verificação em 2 etapas
              </h2>
              <p class="mt-1 text-sm text-muted">
                Um código do app autenticador é pedido a cada login.
              </p>
              <p class="mt-2 text-sm">
                <template v-if="tem2fa === null">
                  <span class="text-muted">Verificando…</span>
                </template>
                <template v-else-if="tem2fa">
                  <UBadge color="success" variant="soft" icon="i-lucide-shield-check">Ativo</UBadge>
                </template>
                <template v-else>
                  <UBadge color="warning" variant="soft" icon="i-lucide-shield-alert">Não configurado</UBadge>
                </template>
              </p>
            </div>
            <UButton
              v-if="tem2fa"
              color="neutral"
              variant="soft"
              icon="i-lucide-refresh-cw"
              label="Reconfigurar"
              @click="reconfigurar2fa"
            />
            <UButton
              v-else-if="tem2fa === false"
              icon="i-lucide-shield-plus"
              label="Configurar"
              @click="navigateTo('/conta/ativar-2fa')"
            />
          </div>
        </UCard>

        <!-- Trocar senha -->
        <UCard>
          <h2 class="font-semibold flex items-center gap-2 mb-4">
            <UIcon name="i-lucide-lock" class="size-5" />
            Trocar senha
          </h2>
          <form class="space-y-4" @submit.prevent="trocarSenha">
            <UFormField label="Senha atual">
              <UInput v-model="senhaAtual" type="password" autocomplete="current-password" class="w-full" />
            </UFormField>
            <UFormField label="Nova senha">
              <UInput v-model="senha" type="password" autocomplete="new-password" class="w-full" />
            </UFormField>
            <UFormField label="Confirmar nova senha">
              <UInput v-model="confirmacao" type="password" autocomplete="new-password" class="w-full" />
            </UFormField>

            <ul class="space-y-1 text-sm">
              <li
                v-for="r in regras"
                :key="r.label"
                class="flex items-center gap-2"
                :class="r.ok ? 'text-success' : 'text-muted'"
              >
                <UIcon :name="r.ok ? 'i-lucide-check-circle-2' : 'i-lucide-circle'" class="size-4 shrink-0" />
                {{ r.label }}
              </li>
              <li class="flex items-center gap-2" :class="coincide ? 'text-success' : 'text-muted'">
                <UIcon :name="coincide ? 'i-lucide-check-circle-2' : 'i-lucide-circle'" class="size-4 shrink-0" />
                As senhas coincidem
              </li>
            </ul>

            <UButton
              type="submit"
              label="Salvar nova senha"
              :loading="salvando"
              :disabled="!podeSalvar"
              icon="i-lucide-check"
            />
          </form>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
