import { serverSupabaseClient, serverSupabaseServiceRole } from '#supabase/server'

const ROLES = ['admin', 'supervisor', 'atendente']

// Edita cargo / ativo / nome de um usuário. Admin only.
export default defineEventHandler(async (event) => {
  await requireAdmin(event)
  const id = getRouterParam(event, 'id')
  const body = await readBody(event) || {}

  const patch: Record<string, any> = {}
  if (ROLES.includes(body.role)) patch.role = body.role
  if (typeof body.active === 'boolean') patch.active = body.active
  if (body.full_name !== undefined) patch.full_name = String(body.full_name)

  if (!Object.keys(patch).length) {
    throw createError({ statusCode: 400, statusMessage: 'Nada para atualizar.' })
  }

  const admin = serverSupabaseServiceRole(event)
  const { error } = await admin.from('profiles').update(patch).eq('id', id)
  if (error) throw createError({ statusCode: 500, statusMessage: error.message })

  const session = await serverSupabaseClient(event)
  await session.rpc('registrar_auditoria', { p_action: 'usuario-editado', p_detail: { id, ...patch } })

  return { ok: true }
})
