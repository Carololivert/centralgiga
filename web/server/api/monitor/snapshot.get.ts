// Proxy autenticado do Monitor SmartOLT: exige admin/supervisor e encaminha
// para o serviço Python interno (../../monitor/server.py). O navegador nunca
// fala direto com o Flask — as credenciais SmartOLT/SGP ficam só naquele serviço.
export default defineEventHandler(async (event) => {
  await requireRole(event, ['admin', 'supervisor'])

  const { monitorApiUrl, monitorApiToken } = useRuntimeConfig()
  const headers = monitorApiToken ? { 'X-Monitor-Token': monitorApiToken } : undefined
  try {
    return await $fetch(`${monitorApiUrl}/api/snapshot`, { timeout: 20000, headers })
  } catch (e) {
    // Se o serviço respondeu 500 com corpo {ok:false, erro}, prefira essa causa
    // real (token inválido, import falhou…); só cai no .message em falha de conexão.
    const err = e as { data?: { erro?: string }, message?: string }
    const causa = err?.data?.erro || err?.message || String(e)
    return { ok: false, erro: `serviço do monitor indisponível: ${causa}` }
  }
})
