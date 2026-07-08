<script setup lang="ts">
definePageMeta({ layout: 'auth' })

const toast = useToast()
const { carregar } = usePerfil()

const senha = ref('')
const confirmacao = ref('')
const mostrar = ref(false)
const salvando = ref(false)

const regras = computed(() => regrasSenha(senha.value))
const coincide = computed(() => confirmacao.value.length > 0 && senha.value === confirmacao.value)
const podeSalvar = computed(() => senhaValida(senha.value) && coincide.value)

async function salvar() {
  if (!podeSalvar.value) return
  salvando.value = true
  try {
    await $fetch('/api/conta/senha', { method: 'POST', body: { senha: senha.value } })
    await carregar(true)
    toast.add({ title: 'Senha definida ✓', color: 'success', icon: 'i-lucide-check' })
    // o porteiro leva para o cadastro de 2FA (ou início)
    await navigateTo('/', { replace: true })
  } catch (e: any) {
    toast.add({
      title: 'Não foi possível salvar',
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
  <UCard>
    <div class="flex flex-col items-center text-center mb-6">
      <AppLogo size="lg" :collapsed="true" class="mb-3" />
      <h1 class="text-lg font-semibold">Crie sua senha</h1>
      <p class="text-sm text-muted">
        Sua senha atual é provisória. Defina uma senha pessoal para continuar.
      </p>
    </div>

    <form class="space-y-4" @submit.prevent="salvar">
      <UFormField label="Nova senha">
        <UInput
          v-model="senha"
          :type="mostrar ? 'text' : 'password'"
          placeholder="••••••••"
          icon="i-lucide-lock"
          autocomplete="new-password"
          class="w-full"
        >
          <template #trailing>
            <UButton
              :icon="mostrar ? 'i-lucide-eye-off' : 'i-lucide-eye'"
              color="neutral"
              variant="link"
              size="sm"
              :padded="false"
              @click="mostrar = !mostrar"
            />
          </template>
        </UInput>
      </UFormField>

      <UFormField label="Confirmar senha">
        <UInput
          v-model="confirmacao"
          :type="mostrar ? 'text' : 'password'"
          placeholder="••••••••"
          icon="i-lucide-lock"
          autocomplete="new-password"
          class="w-full"
        />
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
        <li
          class="flex items-center gap-2"
          :class="coincide ? 'text-success' : 'text-muted'"
        >
          <UIcon :name="coincide ? 'i-lucide-check-circle-2' : 'i-lucide-circle'" class="size-4 shrink-0" />
          As senhas coincidem
        </li>
      </ul>

      <UButton
        type="submit"
        label="Salvar e continuar"
        block
        size="lg"
        :loading="salvando"
        :disabled="!podeSalvar"
        icon="i-lucide-shield-check"
      />
    </form>
  </UCard>
</template>
