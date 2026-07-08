import { serverSupabaseClient, serverSupabaseServiceRole } from '#supabase/server'

// Rejeita uma avaliação. Escrita via sessão do admin (RLS); auditoria via
// service_role (registrar_auditoria é service_role-only). Antes ficava no
// cliente, o que expunha o registrar_auditoria a qualquer usuário logado.
export default defineEventHandler(async (event) => {
  const me = await requireAdmin(event)
  const id = getRouterParam(event, 'id')
  if (!id) throw createError({ statusCode: 400, statusMessage: 'ID ausente.' })

  const client = await serverSupabaseClient(event)
  const { error } = await client
    .from('giganet_reviews')
    .update({ status: 'rejected', final_response: null, decided_at: new Date().toISOString() })
    .eq('id', id)
  if (error) throw createError({ statusCode: 500, statusMessage: error.message })

  const admin = serverSupabaseServiceRole(event)
  await admin.rpc('registrar_auditoria', {
    p_action: 'avaliacao-rejeitada',
    p_detail: { id },
    p_user_id: me.id,
  })

  return { ok: true }
})
