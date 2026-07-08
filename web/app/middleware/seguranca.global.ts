/**
 * Porteiro de segurança (roda em toda navegação, no cliente).
 *
 * Ordem das travas para um usuário logado:
 *   1) Senha provisória  → obriga definir senha própria (/conta/definir-senha)
 *   2) Sem 2FA           → obriga cadastrar 2FA          (/conta/ativar-2fa)
 *   3) Tem 2FA mas sessão não elevada → completa o desafio no /login
 *
 * O redirect de "não logado → /login" já é feito pelo @nuxtjs/supabase.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  // Só no cliente: evita ler sessão/MFA durante o SSR.
  if (import.meta.server) return

  const user = useSupabaseUser()
  if (!user.value) return // não logado → o módulo supabase cuida

  // Páginas públicas nunca são bloqueadas.
  if (to.path === '/login' || to.path === '/confirm') return

  const DEFINIR_SENHA = '/conta/definir-senha'
  const ATIVAR_2FA = '/conta/ativar-2fa'

  const { perfil, carregar } = usePerfil()
  if (!perfil.value) await carregar()
  if (!perfil.value) return // sem perfil (raro) → deixa seguir; role.ts trata

  // 1) Senha provisória → tem de definir senha própria antes de tudo.
  if (perfil.value.must_change_password) {
    return to.path === DEFINIR_SENHA ? undefined : navigateTo(DEFINIR_SENHA)
  }
  // Já trocou: não deixa ficar preso na tela de definir senha.
  if (to.path === DEFINIR_SENHA) return navigateTo('/')

  // 2) 2FA obrigatório para todos.
  //    (Para tornar por-cargo no futuro, condicione ao perfil.value.role.)
  const supabase = useSupabaseClient()
  const { data: aal } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel()

  // Sem nenhum fator verificado → cadastrar 2FA.
  if (!aal || aal.nextLevel !== 'aal2') {
    return to.path === ATIVAR_2FA ? undefined : navigateTo(ATIVAR_2FA)
  }

  // Tem fator, mas a sessão ainda está em aal1 → completar o desafio no login.
  if (aal.currentLevel === 'aal1') {
    return navigateTo('/login')
  }

  // Tudo certo (aal2): não deixa ficar preso na tela de cadastro de 2FA.
  if (to.path === ATIVAR_2FA) return navigateTo('/')
})
