import { serverSupabaseServiceRole } from '#supabase/server'

// Admin gera uma NOVA senha provisória para um usuário (esqueceu a senha).
// Devolve a senha uma única vez e reativa a obrigação de troca no próximo acesso.
export default defineEventHandler(async (event) => {
  const me = await requireAdmin(event)
  const id = getRouterParam(event, 'id')
  if (!id) throw createError({ statusCode: 400, statusMessage: 'ID ausente.' })

  const senhaProvisoria = gerarSenhaProvisoria()

  const admin = serverSupabaseServiceRole(event)
  const { error } = await admin.auth.admin.updateUserById(id, { password: senhaProvisoria })
  if (error) throw createError({ statusCode: 400, statusMessage: error.message })

  await admin.from('profiles').update({ must_change_password: true }).eq('id', id)

  await admin.rpc('registrar_auditoria', { p_action: 'senha-resetada', p_detail: { id }, p_user_id: me.id })

  return { ok: true, senha_provisoria: senhaProvisoria }
})
