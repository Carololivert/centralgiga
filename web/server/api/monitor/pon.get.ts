// Drill-down de uma PON cruzada com o SGP. Mesmo gate (admin/supervisor) e
// mesmo proxy do snapshot; repassa os parâmetros olt/board/port/janela.
export default defineEventHandler(async (event) => {
  await requireRole(event, ['admin', 'supervisor'])

  const { monitorApiUrl, monitorApiToken } = useRuntimeConfig()
  const headers = monitorApiToken ? { 'X-Monitor-Token': monitorApiToken } : undefined
  const query = getQuery(event)
  try {
    return await $fetch(`${monitorApiUrl}/api/pon`, { query, timeout: 60000, headers })
  } catch (e) {
    // Prefira o corpo {ok:false, erro} do serviço (causa real) ao message genérico.
    const err = e as { data?: { erro?: string }, message?: string }
    const causa = err?.data?.erro || err?.message || String(e)
    return { ok: false, erro: `serviço do monitor indisponível: ${causa}` }
  }
})
