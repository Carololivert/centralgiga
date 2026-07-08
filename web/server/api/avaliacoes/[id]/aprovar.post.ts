import { serverSupabaseClient, serverSupabaseServiceRole } from '#supabase/server'
import type { GiganetReview } from '~/types/db'

// Aprova: publica no Google via n8n (N8N_PUBLICAR_URL) e, se der certo,
// marca approved. Leitura/escrita da avaliação via sessão do admin (RLS);
// auditoria via service_role (registrar_auditoria é service_role-only).
export default defineEventHandler(async (event) => {
  const me = await requireAdmin(event)
  const id = getRouterParam(event, 'id')
  const cfg = useRuntimeConfig()
  const body = await readBody(event) || {}
  const client = await serverSupabaseClient(event)

  const { data: review } = await client
    .from('giganet_reviews')
    .select('*')
    .eq('id', id)
    .single<GiganetReview>()
  if (!review) throw createError({ statusCode: 404, statusMessage: 'não encontrada' })
  if (review.status !== 'pending') throw createError({ statusCode: 409, statusMessage: 'já decidida' })

  const finalText = String(body.final_response ?? review.ai_response).slice(0, 4000)
  if (!review.review_id) {
    throw createError({ statusCode: 400, statusMessage: 'review_id ausente — não dá pra publicar no Google' })
  }
  if (!cfg.n8nPublicarUrl) {
    throw createError({ statusCode: 500, statusMessage: 'N8N_PUBLICAR_URL não configurado' })
  }

  try {
    await $fetch(cfg.n8nPublicarUrl as string, {
      method: 'POST',
      body: { review_id: review.review_id, response: finalText },
    })
  } catch (e: any) {
    throw createError({ statusCode: 502, statusMessage: e?.message || 'falha ao chamar n8n' })
  }

  const { error } = await client
    .from('giganet_reviews')
    .update({ status: 'approved', final_response: finalText, decided_at: new Date().toISOString() })
    .eq('id', id)
  if (error) throw createError({ statusCode: 500, statusMessage: error.message })

  const admin = serverSupabaseServiceRole(event)
  await admin.rpc('registrar_auditoria', {
    p_action: 'avaliacao-aprovada',
    p_detail: { id, review_id: review.review_id },
    p_user_id: me.id,
  })

  return { ok: true }
})
