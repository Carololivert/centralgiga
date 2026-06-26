import { createClient } from '@supabase/supabase-js'

// n8n insere uma avaliação pendente aqui. Protegido por x-webhook-secret.
// Insere via RPC security-definer (webhook_inserir_avaliacao) — sem service_role.
export default defineEventHandler(async (event) => {
  const cfg = useRuntimeConfig()
  const secret = cfg.giganetWebhookSecret as string
  if (!secret) {
    throw createError({ statusCode: 500, statusMessage: 'GIGANET_WEBHOOK_SECRET não configurado' })
  }
  if (getHeader(event, 'x-webhook-secret') !== secret) {
    throw createError({ statusCode: 401, statusMessage: 'unauth' })
  }

  const body = await readBody(event) || {}

  // Google às vezes manda "(Translated by Google) <pt>\n\n(Original)\n<...>"
  const comment = body.comment
    ? String(body.comment)
        .replace(/^\s*\(Translated by Google\)\s*/i, '')
        .replace(/\s*\(Original\)[\s\S]*$/i, '')
        .trim()
    : ''

  if (!body.ai_response || typeof body.ai_response !== 'string') {
    throw createError({ statusCode: 400, statusMessage: 'ai_response obrigatório' })
  }

  const sb = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_KEY!)
  const { data, error } = await sb.rpc('webhook_inserir_avaliacao', {
    p_secret: secret,
    p_review_id: body.review_id ? String(body.review_id) : '',
    p_reviewer_name: body.reviewer_name ? String(body.reviewer_name) : '',
    p_star_rating: typeof body.star_rating === 'number' ? body.star_rating : null,
    p_comment: comment,
    p_ai_response: String(body.ai_response),
    p_resume_url: body.resume_url ? String(body.resume_url) : '',
  })

  if (error) throw createError({ statusCode: 500, statusMessage: error.message })
  return { review: data }
})
