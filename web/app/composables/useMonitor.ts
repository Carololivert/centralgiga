import type { Snapshot, SnapshotResp, PonResp, PonRef } from '~/types/monitor'

const REFRESH_SECS = 30

// Timer único (módulo). Como a página /monitor liga com iniciar() e desliga com
// parar(), o polling não continua rodando quando o supervisor sai da tela.
let timer: ReturnType<typeof setInterval> | null = null

export function useMonitor() {
  const snapshot = useState<Snapshot | null>('mon:snapshot', () => null)
  const carregando = useState<boolean>('mon:loading', () => false)
  const erro = useState<string | null>('mon:erro', () => null)
  const countdown = useState<number>('mon:countdown', () => REFRESH_SECS)
  const iniciado = useState<boolean>('mon:started', () => false)

  const health = computed(() => snapshot.value?.health ?? 'ok')
  const demo = computed(() => snapshot.value?.demo === true)
  const geradoEm = computed(() => snapshot.value?.generated_at ?? null)

  async function refresh() {
    // Guarda de concorrência: uma resposta lenta e antiga não sobrescreve dados novos.
    if (carregando.value) return
    carregando.value = true
    countdown.value = REFRESH_SECS
    try {
      const r = await $fetch<SnapshotResp>('/api/monitor/snapshot', { timeout: 20000 })
      if (!r.ok || !r.data) {
        erro.value = r.erro || 'Resposta inválida do serviço do monitor'
      } else {
        snapshot.value = r.data
        erro.value = null
      }
    } catch (e) {
      erro.value = (e as Error)?.message || 'Falha ao contatar o monitor'
    } finally {
      carregando.value = false
    }
  }

  function tick() {
    countdown.value -= 1
    if (countdown.value <= 0) {
      countdown.value = REFRESH_SECS
      refresh()
    }
  }

  // Chamado no onMounted da página /monitor. 1ª carga + timer de 1s.
  function iniciar() {
    if (iniciado.value) return
    iniciado.value = true
    refresh()
    if (import.meta.client && !timer) timer = setInterval(tick, 1000)
  }

  // Chamado no onUnmounted: para o polling ao sair da tela.
  function parar() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    iniciado.value = false
  }

  async function fetchPon(ref: PonRef, janela: number): Promise<PonResp> {
    return await $fetch<PonResp>('/api/monitor/pon', {
      query: { olt: ref.olt, board: ref.board, port: ref.port, janela },
      timeout: 60000,
    })
  }

  return {
    snapshot, carregando, erro, countdown,
    health, demo, geradoEm,
    refresh, iniciar, parar, fetchPon,
    REFRESH_SECS,
  }
}
