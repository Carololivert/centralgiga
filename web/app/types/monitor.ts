// Tipos do payload do serviço Python do Monitor (../../monitor/server.py),
// entregue à Central pelas rotas server/api/monitor/*. O Flask já manda tudo
// formatado (caiu_fmt, idade, temp_num, percent…) — o front só apresenta.

export type Health = 'ok' | 'warn' | 'crit'
export type FibraKind = 'partial_los' | 'los'
export type EnergiaKind = 'power' | 'offline'

export interface Olt {
  id: string
  nome: string
  temp: string | null // "31°C"
  temp_num: number | null
  quente: boolean
  uptime: string
}

export interface TotalItem {
  pons: number
  subs: number
}

export interface Totais {
  partial_los: TotalItem
  los: TotalItem
  power: TotalItem
  offline: TotalItem
}

export interface EventoFibra {
  olt: string
  olt_id: string
  kind: FibraKind
  regiao: string
  cidade: string
  board: number | string
  port: number | string
  total_onus: number
  los: number
  power: number
  offline: number
  percent: number
  caiu_em: string | null
  caiu_fmt: string | null
  idade_min: number | null
  idade: string
  novo: boolean
}

export interface EventoEnergia {
  olt: string
  kind: EnergiaKind
  regiao: string
  cidade: string
  subs: number
  caiu_em: string | null
  caiu_fmt: string | null
  idade_min: number | null
  idade: string
}

export interface Snapshot {
  generated_at: string
  olts: Olt[]
  totais: Totais
  health: Health
  eventos_fibra: EventoFibra[]
  eventos_energia: EventoEnergia[]
  demo?: boolean
}

export interface SnapshotResp {
  ok: boolean
  data?: Snapshot
  erro?: string
}

// --- Drill-down da PON (/api/monitor/pon) -------------------------------

export interface Cliente {
  onu_sn: string | null
  onu_status: string | null // Online | LOS | Power fail | Offline | null
  caiu_em: string | null
  caiu_fmt: string | null
  olt_id: string | number | null
  board: number | string | null
  port: number | string | null
  onu: number | string | null
  name_olt: string | null
  address_olt: string | null
  nome: string | null
  cpfcnpj: string | null
  endereco: string | null
  contrato_id: string | number | null
  contrato_status: string | null // Ativo | Cancelado | null
  plano: string | null
  telefones: string[]
  via: string | null
  fonte: 'sgp' | 'smartolt'
}

export interface GrupoQueda {
  motivo: string
  motivo_label: string
  n: number
  ativos: number
  caiu_fmt: string | null
  span_min: number
  clientes: Cliente[]
}

export interface PonResp {
  ok: boolean
  total_pon: number
  down: number
  ativos_down: number
  capped: boolean
  janela: number
  grupos: GrupoQueda[]
  sem_hora: Cliente[]
  clientes: Cliente[]
  demo?: boolean
  erro?: string
}

export interface PonRef {
  olt: string
  board: string
  port: string
  regiao: string
}
