import { serverSupabaseClient, serverSupabaseServiceRole } from '#supabase/server'

const ROLES = ['admin', 'supervisor', 'atendente']

// Cria um usuário (auth + profile). Admin only. service_role server-side.
export default defineEventHandler(async (event) => {
  await requireAdmin(event)
  const body = await readBody(event) || {}

  const email = String(body.email || '').trim().toLowerCase()
  const password = String(body.password || '')
  const full_name = String(body.full_name || '').trim()
  const role = ROLES.includes(body.role) ? body.role : 'atendente'

  if (!email || password.length < 6) {
    throw createError({ statusCode: 400, statusMessage: 'E-mail e senha (mín. 6 caracteres) são obrigatórios.' })
  }

  const admin = serverSupabaseServiceRole(event)
  const { data, error } = await admin.auth.admin.createUser({
    email,
    password,
    email_confirm: true, // já entra sem precisar confirmar e-mail
    user_metadata: { full_name, role },
  })
  if (error) throw createError({ statusCode: 400, statusMessage: error.message })

  // o trigger já cria o profile; reforça nome/cargo/ativo
  await admin.from('profiles').update({ full_name, role, active: true }).eq('id', data.user.id)

  const session = await serverSupabaseClient(event)
  await session.rpc('registrar_auditoria', { p_action: 'usuario-criado', p_detail: { email, role } })

  return { ok: true, id: data.user.id }
})
