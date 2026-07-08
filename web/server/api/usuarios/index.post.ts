import { serverSupabaseServiceRole } from '#supabase/server'

const ROLES = ['admin', 'supervisor', 'atendente']

// Cria um usuário (auth + profile) com SENHA PROVISÓRIA gerada pelo sistema.
// Admin only. A senha é devolvida uma única vez para o admin repassar; no
// primeiro acesso o usuário é obrigado a definir a própria senha.
export default defineEventHandler(async (event) => {
  const me = await requireAdmin(event)
  const body = await readBody(event) || {}

  const email = String(body.email || '').trim().toLowerCase()
  const full_name = String(body.full_name || '').trim()
  const role = ROLES.includes(body.role) ? body.role : 'atendente'

  if (!email || !email.includes('@')) {
    throw createError({ statusCode: 400, statusMessage: 'Informe um e-mail válido.' })
  }

  const senhaProvisoria = gerarSenhaProvisoria()

  const admin = serverSupabaseServiceRole(event)
  const { data, error } = await admin.auth.admin.createUser({
    email,
    password: senhaProvisoria,
    email_confirm: true, // já entra sem precisar confirmar e-mail
    user_metadata: { full_name, role },
  })
  if (error) throw createError({ statusCode: 400, statusMessage: error.message })

  // o trigger cria o profile INATIVO (fail-closed); aqui o admin o ativa e
  // define nome/cargo + marca senha provisória. Se falhar, o usuário fica
  // inerte (active=false) — então avisamos o admin em vez de retornar ok.
  const { error: upErr } = await admin
    .from('profiles')
    .update({ full_name, role, active: true, must_change_password: true })
    .eq('id', data.user.id)
  if (upErr) {
    throw createError({ statusCode: 500, statusMessage: 'Usuário criado, mas falha ao ativar o perfil. Ative/edite manualmente na lista.' })
  }

  await admin.rpc('registrar_auditoria', { p_action: 'usuario-criado', p_detail: { email, role }, p_user_id: me.id })

  return { ok: true, id: data.user.id, senha_provisoria: senhaProvisoria }
})
