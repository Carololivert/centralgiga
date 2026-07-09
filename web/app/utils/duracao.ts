// Helpers de tempo/duração para os marcadores de execução das automações.
// Auto-importados pelo Nuxt (app/utils/).

import type { Job } from '~/types/db'

/** Duração legível a partir de milissegundos: "18s", "1m 20s", "1h 3m". */
export function formatarDuracao(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return ''
  const totalSeg = Math.round(ms / 1000)
  if (totalSeg < 60) return `${totalSeg}s`
  const min = Math.floor(totalSeg / 60)
  const seg = totalSeg % 60
  if (min < 60) return seg ? `${min}m ${seg}s` : `${min}m`
  const h = Math.floor(min / 60)
  const m = min % 60
  return m ? `${h}h ${m}m` : `${h}h`
}

/** Cronômetro no formato m:ss (para o tempo correndo enquanto executa). */
export function cronometro(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) ms = 0
  const totalSeg = Math.floor((ms as number) / 1000)
  const min = Math.floor(totalSeg / 60)
  const seg = totalSeg % 60
  return `${min}:${String(seg).padStart(2, '0')}`
}

/**
 * Milissegundos de execução de um job concluído/com erro.
 * Usa started_at (quando o worker pegou) → finished_at; cai para created_at
 * se started_at faltar. Retorna null se ainda não terminou.
 */
export function duracaoJobMs(job: Pick<Job, 'created_at' | 'started_at' | 'finished_at'> | null | undefined): number | null {
  if (!job?.finished_at) return null
  const inicio = job.started_at || job.created_at
  if (!inicio) return null
  const ms = new Date(job.finished_at).getTime() - new Date(inicio).getTime()
  return ms >= 0 ? ms : null
}

/**
 * Milissegundos decorridos de um job EM ANDAMENTO até "agora".
 * Conta de started_at (se já executando) ou created_at (ainda na fila).
 */
export function decorridoJobMs(
  job: Pick<Job, 'created_at' | 'started_at'> | null | undefined,
  agoraMs: number,
): number | null {
  if (!job) return null
  const inicio = job.started_at || job.created_at
  if (!inicio) return null
  const ms = agoraMs - new Date(inicio).getTime()
  return ms >= 0 ? ms : 0
}
