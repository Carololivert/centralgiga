import { serverSupabaseClient, serverSupabaseUser } from '#supabase/server'
import type { H3Event } from 'h3'

/** Garante que o chamador está logado e é admin (usa a sessão, sem service_role). */
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
