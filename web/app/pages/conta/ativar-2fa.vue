<script setup lang="ts">
definePageMeta({ layout: 'auth' })

const supabase = useSupabaseClient()
const toast = useToast()
const { carregar } = usePerfil()

const carregando = ref(true)
const salvando = ref(false)
const erro = ref('')

const qr = ref('')
const secret = ref('')
const factorId = ref('')
const codigo = ref('')

// o qr_code pode vir como data-URI (<img>) ou como SVG cru (v-html)
const qrEhImagem = computed(() => qr.value.startsWith('data:'))

async function limparNaoVerificados() {
  const { data } = await supabase.auth.mfa.listFactors()
  for (const f of (data?.all || [])) {
    if (f.status !== 'verified') {
      await supabase.auth.mfa.unenroll({ factorId: f.id })
    }
  }
}

async function iniciar() {
  carregando.value = true
  erro.value = ''
  try {
    // já tem 2FA? então não precisa cadastrar de novo.
    const { data: aal } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel()
    if (aal?.nextLevel === 'aal2') {
      await navigateTo('/', { replace: true })
      return
    }
    await limparNaoVerificados()
    const { data, error } = await supabase.auth.mfa.enroll({ factorType: 'totp' })
    if (error || !data) throw error || new Error('Falha ao gerar o QR Code.')
    factorId.value = data.id
    qr.value = data.totp.qr_code
    secret.value = data.totp.secret
  } catch (e: any) {
    erro.value = e?.message || 'Erro ao iniciar o 2FA.'
  } finally {
    carregando.value = false
  }
}
onMounted(iniciar)

async function confirmar() {
  const code = codigo.value.trim()
  if (!factorId.value || code.length < 6) return
  salvando.value = true
  try {
    const { data: ch, error: e1 } = await supabase.auth.mfa.challenge({ factorId: factorId.value })
    if (e1 || !ch) throw e1 || new Error('Falha ao verificar.')
    const { error: e2 } = await supabase.auth.mfa.verify({
      factorId: factorId.value,
      challengeId: ch.id,
      code,
    })
    if (e2) throw e2
    await carregar(true)
    toast.add({ title: '2FA ativado ✓', color: 'success', icon: 'i-lucide-shield-check' })
    await navigateTo('/', { replace: true })
  } catch {
    toast.add({
      title: 'Código inválido',
      description: 'Confira o código de 6 dígitos no app e tente de novo.',
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
      <h1 class="text-lg font-semibold">Ative a verificação em 2 etapas</h1>
      <p class="text-sm text-muted">
        Escaneie o QR Code com um app autenticador (Google Authenticator, Authy…)
        e digite o código gerado.
      </p>
    </div>

    <div v-if="carregando" class="flex justify-center py-12 text-muted">
      <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin" />
    </div>

    <UAlert
      v-else-if="erro"
      color="error"
      variant="soft"
      icon="i-lucide-triangle-alert"
      title="Não foi possível iniciar o 2FA"
      :description="erro"
      :actions="[{ label: 'Tentar de novo', color: 'neutral', variant: 'soft', onClick: iniciar }]"
    />

    <div v-else class="space-y-5">
      <div class="flex justify-center">
        <div class="rounded-xl border border-default bg-white p-3">
          <img v-if="qrEhImagem" :src="qr" alt="QR Code do 2FA" width="180" height="180">
          <div v-else class="[&_svg]:size-[180px]" v-html="qr" />
        </div>
      </div>

      <div class="text-center text-sm text-muted">
        <p>Não consegue escanear? Digite este código no app:</p>
        <code class="mt-1 inline-block rounded bg-elevated px-2 py-1 font-mono text-default tracking-wider break-all">
          {{ secret }}
        </code>
      </div>

      <form class="space-y-3" @submit.prevent="confirmar">
        <UFormField label="Código de 6 dígitos">
          <UInput
            v-model="codigo"
            inputmode="numeric"
            maxlength="6"
            placeholder="000000"
            icon="i-lucide-key-round"
            autocomplete="one-time-code"
            class="w-full text-center tracking-[0.4em]"
          />
        </UFormField>
        <UButton
          type="submit"
          label="Ativar 2FA"
          block
          size="lg"
          :loading="salvando"
          :disabled="codigo.trim().length < 6"
          icon="i-lucide-shield-check"
        />
      </form>
    </div>
  </UCard>
</template>
