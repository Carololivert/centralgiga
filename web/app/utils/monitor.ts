// Helpers de apresentação do Monitor. O Flask já manda quase tudo formatado;
// aqui ficam só mapeamentos de cor/rótulo e a barra de porcentagem.

import type { Health } from '~/types/monitor'

/** Largura (0–100) da barrinha de % de afetados, com um mínimo visível. */
export function barWidth(percent: number): number {
  return Math.max(3, Math.min(100, Math.round(percent || 0)))
}

/** Cor semântica do estado de uma ONU (status caído/online). */
export function onuColor(status: string | null | undefined): string {
  if (status === 'Online') return 'text-success'
  if (status == null) return 'text-muted'
  return 'text-error'
}

/** Cor (Nuxt UI) do badge conforme o motivo de queda. */
export function motivoColor(motivo: string): 'error' | 'info' | 'neutral' {
  if (motivo === 'LOS') return 'error'
  if (motivo === 'Power fail') return 'info'
  return 'neutral'
}

export interface HealthMeta {
  color: 'success' | 'warning' | 'error'
  icon: string
  titulo: string
  descricao: string
}

/** Metadados de UI para cada nível de saúde geral da rede. */
export function healthMeta(h: Health): HealthMeta {
  if (h === 'crit') {
    return {
      color: 'error',
      icon: 'i-lucide-siren',
      titulo: 'CRÍTICO',
      descricao: 'rompimento total (LOS) ou onset recente — verificar agora',
    }
  }
  if (h === 'warn') {
    return {
      color: 'warning',
      icon: 'i-lucide-triangle-alert',
      titulo: 'ATENÇÃO',
      descricao: 'há PONs com perda parcial de sinal',
    }
  }
  return {
    color: 'success',
    icon: 'i-lucide-shield-check',
    titulo: 'TUDO OK',
    descricao: 'sem eventos de rompimento no momento',
  }
}
