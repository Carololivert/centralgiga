<script setup lang="ts">
import type { FormError } from '@nuxt/ui'

definePageMeta({ layout: 'auth' })

const supabase = useSupabaseClient()
const user = useSupabaseUser()
const toast = useToast()
const { carregar } = usePerfil()

const state = reactive({ email: '', senha: '' })
const carregando = ref(false)

watchEffect(() => {
  if (user.value) navigateTo('/', { replace: true })
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

async function entrar() {
  carregando.value = true
  try {
    const { error } = await supabase.auth.signInWithPassword({
      email: state.email.trim(),
      password: state.senha,
    })
    if (error) throw error
    await carregar(true)
    await navigateTo('/', { replace: true })
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
</script>

<template>
  <UCard>
    <div class="flex flex-col items-center text-center mb-6">
      <AppLogo size="lg" :collapsed="true" class="mb-3" />
      <h1 class="text-lg font-semibold">
        Central Giganet
      </h1>
      <p class="text-sm text-muted">Acesso restrito · entre com seu e-mail</p>
    </div>

    <UForm :state="state" :validate="validate" class="space-y-4" @submit="entrar">
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
  </UCard>
</template>
