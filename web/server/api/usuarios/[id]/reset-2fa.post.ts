import { serverSupabaseServiceRole } from '#supabase/server'

// Admin remove os fatores de 2FA de um usuário (perdeu o celular/authenticator).
// No próximo acesso ele será obrigado a cadastrar o 2FA de novo.
export default defineEventHandler(async (event) => {
  const me = await requireAdmin(event)
  const id = getRouterParam(event, 'id')
  if (!id) throw createError({ statusCode: 400, statusMessage: 'ID ausente.' })

  const admin = serverSupabaseServiceRole(event)
  const { data, error } = await admin.auth.admin.getUserById(id)
  if (error || !data?.user) {
    throw createError({ statusCode: 404, statusMessage: 'Usuário não encontrado.' })
  }

  const factors = ((data.user as any).factors || []) as Array<{ id: string }>
  for (const f of factors) {
    await admin.auth.admin.mfa.deleteFactor({ id: f.id, userId: id })
  }

  await admin.rpc('registrar_auditoria', { p_action: '2fa-resetado', p_detail: { id, fatores: factors.length }, p_user_id: me.id })

  return { ok: true, removidos: factors.length }
})
