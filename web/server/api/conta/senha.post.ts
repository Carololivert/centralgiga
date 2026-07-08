import { serverSupabaseUser, serverSupabaseServiceRole } from '#supabase/server'
import { createClient } from '@supabase/supabase-js'

// Troca a senha do próprio usuário logado.
//  • 1º acesso (must_change_password): só a nova senha (já está autenticado
//    com a provisória).
//  • Troca voluntária: exige a senha atual para confirmar a identidade.
export default defineEventHandler(async (event) => {
  const user = await serverSupabaseUser(event).catch(() => null)
  if (!user) throw createError({ statusCode: 401, statusMessage: 'Não autenticado' })

  const body = await readBody(event) || {}
  const senha = String(body.senha || '')
  const senhaAtual = String(body.senha_atual || '')

  const erro = validarSenhaForte(senha)
  if (erro) throw createError({ statusCode: 400, statusMessage: erro })

  const admin = serverSupabaseServiceRole(event)

  const { data: perfil } = await admin
    .from('profiles')
    .select('must_change_password')
    .eq('id', user.id)
    .single()
  const obrigatoria = (perfil as any)?.must_change_password === true

  const cfg = useRuntimeConfig()
  const anon = createClient(
    cfg.public.supabase.url,
    cfg.public.supabase.key,
    { auth: { persistSession: false, autoRefreshToken: false } },
  )

  // Troca voluntária: confere a senha atual antes de permitir.
  if (!obrigatoria) {
    if (!senhaAtual) {
      throw createError({ statusCode: 400, statusMessage: 'Informe a senha atual.' })
    }
    const { error: e } = await anon.auth.signInWithPassword({
      email: user.email!,
      password: senhaAtual,
    })
    if (e) throw createError({ statusCode: 400, statusMessage: 'Senha atual incorreta.' })
  }

  // A nova senha não pode ser igual à atual. Vale também para o 1º acesso:
  // impede "trocar" a senha provisória por ela mesma (que o admin já viu).
  const { error: igual } = await anon.auth.signInWithPassword({
    email: user.email!,
    password: senha,
  })
  if (!igual) {
    throw createError({ statusCode: 400, statusMessage: 'A nova senha deve ser diferente da senha atual.' })
  }

  const { error } = await admin.auth.admin.updateUserById(user.id, { password: senha })
  if (error) throw createError({ statusCode: 400, statusMessage: error.message })

  const { error: upErr } = await admin
    .from('profiles')
    .update({ must_change_password: false, password_changed_at: new Date().toISOString() })
    .eq('id', user.id)
  if (upErr) {
    throw createError({ statusCode: 500, statusMessage: 'Senha alterada, mas houve falha ao atualizar o perfil. Tente entrar novamente.' })
  }

  await admin.rpc('registrar_auditoria', {
    p_action: obrigatoria ? 'senha-definida-1o-acesso' : 'senha-trocada',
    p_detail: {},
    p_user_id: user.id,
  })

  return { ok: true }
})
