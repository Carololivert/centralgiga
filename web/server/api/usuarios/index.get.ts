import { serverSupabaseServiceRole } from '#supabase/server'

// Lista usuários (auth.users + profiles). Admin only. service_role server-side.
export default defineEventHandler(async (event) => {
  await requireAdmin(event)
  const admin = serverSupabaseServiceRole(event)

  const { data: list, error } = await admin.auth.admin.listUsers({ page: 1, perPage: 200 })
  if (error) throw createError({ statusCode: 500, statusMessage: error.message })

  const { data: perfis } = await admin.from('profiles').select('id, full_name, role, active, must_change_password')
  const pmap = new Map((perfis ?? []).map((p: any) => [p.id, p]))

  // ids com 2FA verificado (função security definer que lê auth.mfa_factors)
  const { data: com2fa } = await admin.rpc('usuarios_com_2fa')
  const set2fa = new Set<string>(((com2fa ?? []) as any[]).map((r: any) => (typeof r === 'string' ? r : r.usuarios_com_2fa)))

  const users = (list?.users ?? []).map((u) => {
    const p: any = pmap.get(u.id) ?? {}
    return {
      id: u.id,
      email: u.email,
      full_name: p.full_name ?? '',
      role: p.role ?? 'atendente',
      active: p.active ?? true,
      must_change_password: p.must_change_password ?? false,
      has_2fa: set2fa.has(u.id),
      created_at: u.created_at,
    }
  })
  return { users }
})
