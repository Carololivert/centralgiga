<script setup lang="ts">
import type { FormError } from '@nuxt/ui'

definePageMeta({ layout: 'auth' })

const supabase = useSupabaseClient()
const user = useSupabaseUser()
const toast = useToast()
const route = useRoute()
const { carregar } = usePerfil()

// watch (não onMounted): o logout por inatividade navega para /login?motivo=…
// com o componente já montado — a query muda sem remontar, então o toast
// precisa reagir à query, não ao mount.
watch(
  () => route.query.motivo,
  (m) => {
    if (m === 'inatividade') {
      toast.add({
        title: 'Sessão encerrada',
        description: 'Você ficou mais de 1 hora sem atividade e foi desconectado por segurança.',
        color: 'warning',
        icon: 'i-lucide-clock',
      })
    }
  },
  { immediate: true },
)

const etapa = ref<'senha' | 'mfa'>('senha')
const state = reactive({ email: '', senha: '' })
const codigo = ref('')
const carregando = ref(false)
const desafio = ref<{ factorId: string, challengeId: string } | null>(null)

// Decide o próximo passo após ter uma sessão válida.
// Retorna true se pode seguir para o app; false se abriu o desafio de 2FA.
async function rotear(): Promise<boolean> {
  const { data } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel()
  if (data && data.currentLevel === 'aal1' && data.nextLevel === 'aal2') {
    await iniciarDesafio()
    return false
  }
  return true
}

// Sessão já existente (ex.: recarregou a página logado): decide o rumo.
watchEffect(async () => {
  if (user.value && etapa.value === 'senha' && !carregando.value) {
    const ok = await rotear()
    if (ok) navigateTo('/', { replace: true })
  }
})

// Se a sessão cair (ex.: logout por inatividade parado na etapa do 2FA),
// volta o formulário para a etapa de senha em vez de deixar um desafio inválido.
watch(user, (u) => {
  if (!u) {
    etapa.value = 'senha'
    desafio.value = null
    codigo.value = ''
    carregando.value = false
  }
})

function validate(s: typeof state): FormError[] {
  const e: FormError[] = []
  if (!s.email.trim()) e.push({ name: 'email', message: 'Informe o e-mail.' })
  if (!s.senha) e.push({ name: 'senha', message: 'Informe a senha.' })
  return e
}

function traduzErro(msg: string) {
  if (/invalid login credentials/i.test(msg)) return 'E-mail ou senha incorretos.'
  if (/email not confirmed/i.test(msg)) return 'E-mail ainda não confirmado.'
  return msg
}

async function iniciarDesafio() {
  const { data: fatores } = await supabase.auth.mfa.listFactors()
  const totp = fatores?.totp?.find(f => f.status === 'verified') || fatores?.totp?.[0]
  if (!totp) {
    etapa.value = 'senha'
    return
  }
  const { data: ch, error } = await supabase.auth.mfa.challenge({ factorId: totp.id })
  if (error || !ch) {
    toast.add({ title: 'Falha ao iniciar a verificação', color: 'error', icon: 'i-lucide-triangle-alert' })
    return
  }
  desafio.value = { factorId: totp.id, challengeId: ch.id }
  etapa.value = 'mfa'
}

async function entrar() {
  carregando.value = true
  try {
    const { error } = await supabase.auth.signInWithPassword({
      email: state.email.trim(),
      password: state.senha,
    })
    if (error) throw error
    const ok = await rotear()
    if (ok) {
      await carregar(true)
      await navigateTo('/', { replace: true })
    }
  } catch (e) {
    toast.add({
      title: 'Não foi possível entrar',
      description: traduzErro((e as Error).message),
      color: 'error',
      icon: 'i-lucide-triangle-alert',
    })
  } finally {
    carregando.value = false
  }
}

async function verificar() {
  if (!desafio.value) return
  carregando.value = true
  try {
    const { error } = await supabase.auth.mfa.verify({
      factorId: desafio.value.factorId,
      challengeId: desafio.value.challengeId,
      code: codigo.value.trim(),
    })
    if (error) throw error
    await carregar(true)
    await navigateTo('/', { replace: true })
  } catch {
    toast.add({
      title: 'Código inválido',
      description: 'Confira o código de 6 dígitos no app e tente de novo.',
      color: 'error',
      icon: 'i-lucide-triangle-alert',
    })
  } finally {
    carregando.value = false
  }
}

async function voltar() {
  // desiste do 2FA em andamento e volta a poder trocar de conta
  await supabase.auth.signOut()
  etapa.value = 'senha'
  codigo.value = ''
  desafio.value = null
  state.senha = ''
}
</script>

<template>
  <UCard>
    <div class="flex flex-col items-center text-center mb-6">
      <AppLogo size="lg" :collapsed="true" class="mb-3" />
      <h1 class="text-lg font-semibold">Central Giganet</h1>
      <p class="text-sm text-muted">
        {{ etapa === 'senha' ? 'Acesso restrito · entre com seu e-mail' : 'Verificação em 2 etapas' }}
      </p>
    </div>

    <!-- Etapa 1: e-mail + senha -->
    <UForm
      v-if="etapa === 'senha'"
      :state="state"
      :validate="validate"
      class="space-y-4"
      @submit="entrar"
    >
      <UFormField label="E-mail" name="email" required>
        <UInput
          v-model="state.email"
          type="email"
          placeholder="voce@giganet.com"
          icon="i-lucide-mail"
          autocomplete="email"
          class="w-full"
        />
      </UFormField>

      <UFormField label="Senha" name="senha" required>
        <UInput
          v-model="state.senha"
          type="password"
          placeholder="••••••••"
          icon="i-lucide-lock"
          autocomplete="current-password"
          class="w-full"
        />
      </UFormField>

      <UButton
        type="submit"
        label="Entrar"
        block
        size="lg"
        :loading="carregando"
        icon="i-lucide-log-in"
      />
    </UForm>

    <!-- Etapa 2: código do app autenticador -->
    <form v-else class="space-y-4" @submit.prevent="verificar">
      <p class="text-sm text-muted text-center">
        Digite o código de 6 dígitos do seu app autenticador.
      </p>
      <UFormField label="Código">
        <UInput
          v-model="codigo"
          inputmode="numeric"
          maxlength="6"
          placeholder="000000"
          icon="i-lucide-key-round"
          autocomplete="one-time-code"
          autofocus
          class="w-full text-center tracking-[0.4em]"
        />
      </UFormField>
      <UButton
        type="submit"
        label="Verificar e entrar"
        block
        size="lg"
        :loading="carregando"
        :disabled="codigo.trim().length < 6"
        icon="i-lucide-shield-check"
      />
      <UButton
        label="Voltar"
        block
        color="neutral"
        variant="ghost"
        icon="i-lucide-arrow-left"
        @click="voltar"
      />
    </form>
  </UCard>
</template>
