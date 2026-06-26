import { serverSupabaseClient } from '#supabase/server'
import type { GiganetReview } from '~/types/db'

// Pede ao n8n (N8N_REGERAR_URL) uma nova resposta da IA e atualiza a linha.
export default defineEventHandler(async (event) => {
  await requireAdmin(event)
  const id = getRouterParam(event, 'id')
  const cfg = useRuntimeConfig()
  const client = await serverSupabaseClient(event)

  if (!cfg.n8nRegerarUrl) {
    throw createError({ statusCode: 500, statusMessage: 'N8N_REGERAR_URL não configurado' })
  }

  const { data: review } = await client
    .from('giganet_reviews')
    .select('*')
    .eq('id', id)
    .single<GiganetReview>()
  if (!review) throw createError({ statusCode: 404, statusMessage: 'não encontrada' })
  if (review.status !== 'pending') throw createError({ statusCode: 409, statusMessage: 'já decidida' })

  let nova = ''
  try {
    const r: any = await $fetch(cfg.n8nRegerarUrl as string, {
      method: 'POST',
      body: {
        reviewer_name: review.reviewer_name,
        star_rating: review.star_rating,
        comment: review.comment,
      },
    })
    nova = typeof r?.response === 'string' ? r.response.trim() : ''
  } catch (e: any) {
    throw createError({ statusCode: 502, statusMessage: e?.message || 'falha ao chamar n8n' })
  }
  if (!nova) throw createError({ statusCode: 502, statusMessage: 'n8n retornou resposta vazia' })

  const { data, error } = await client
    .from('giganet_reviews')
    .update({ ai_response: nova.slice(0, 4000), final_response: null })
    .eq('id', id)
    .select()
    .single()
  if (error) throw createError({ statusCode: 500, statusMessage: error.message })

  return { review: data }
})
