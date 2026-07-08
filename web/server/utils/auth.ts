import { serverSupabaseClient, serverSupabaseUser } from '#supabase/server'
import type { H3Event } from 'h3'

/**
 * Garante que o chamador está logado e é admin (usa a sessão, sem service_role).
 * Também exige 2FA concluído (AAL2) para ações administrativas — defesa em
 * profundidade: mesmo que alguém pule a tela de 2FA, os endpoints de admin
 * recusam enquanto a sessão não estiver elevada.
 */
export async function requireAdmin(event: H3Event) {
  const user = await serverSupabaseUser(event).catch(() => null)
  if (!user) {
    throw createError({ statusCode: 401, statusMessage: 'Não autenticado' })
  }
  const client = await serverSupabaseClient(event)

  // Exige AAL2 quando conseguimos determinar o nível. Se não der (sessão
  // indisponível no servidor), não bloqueia — a trava principal é o login.
  const { data: aal } = await client.auth.mfa.getAuthenticatorAssuranceLevel()
  if (aal?.currentLevel === 'aal1') {
    throw createError({
      statusCode: 403,
      statusMessage: 'Confirme o 2FA para executar ações administrativas.',
    })
  }

  const { data } = await client
    .from('profiles')
    .select('role, active')
    .eq('id', user.id)
    .single()
  if (!data || (data as any).role !== 'admin' || (data as any).active === false) {
    throw createError({ statusCode: 403, statusMessage: 'Sem permissão' })
  }
  return user
}
