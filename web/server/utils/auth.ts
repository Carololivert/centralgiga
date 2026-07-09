import { serverSupabaseClient, serverSupabaseUser } from '#supabase/server'
import type { H3Event } from 'h3'

/**
 * Garante que o chamador está logado e é admin (usa a sessão, sem service_role).
 *
 * NÃO exige AAL2 aqui: o token que chega ao servidor vem do COOKIE e nem sempre
 * está elevado a aal2 (mesmo para um admin que fez o 2FA no login) — exigir aal2
 * no servidor derrubava as telas de admin (Usuários/Auditoria/Avaliações) com
 * 403 mesmo com o 2FA concluído. A obrigatoriedade de 2FA é imposta no porteiro
 * do app (middleware seguranca.global.ts, que barra quem não tem 2FA antes de
 * qualquer página) e na RLS de jobs_insert (rodar automação exige aal2).
 */
export async function requireAdmin(event: H3Event) {
  const user = await serverSupabaseUser(event).catch(() => null)
  if (!user) {
    throw createError({ statusCode: 401, statusMessage: 'Não autenticado' })
  }
  const client = await serverSupabaseClient(event)

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
