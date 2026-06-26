import { serverSupabaseServiceRole } from '#supabase/server'

// Lista usuários (auth.users + profiles). Admin only. service_role server-side.
export default defineEventHandler(async (event) => {
  await requireAdmin(event)
  const admin = serverSupabaseServiceRole(event)

  const { data: list, error } = await admin.auth.admin.listUsers({ page: 1, perPage: 200 })
  if (error) throw createError({ statusCode: 500, statusMessage: error.message })

  const { data: perfis } = await admin.from('profiles').select('id, full_name, role, active')
  const pmap = new Map((perfis ?? []).map((p: any) => [p.id, p]))

  const users = (list?.users ?? []).map((u) => {
    const p: any = pmap.get(u.id) ?? {}
    return {
      id: u.id,
      email: u.email,
      full_name: p.full_name ?? '',
      role: p.role ?? 'atendente',
      active: p.active ?? true,
      created_at: u.created_at,
    }
  })
  return { users }
})
