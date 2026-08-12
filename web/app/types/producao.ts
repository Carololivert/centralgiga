/**
 * Tipos do dashboard de Produção.
 *
 * Espelham o que o worker grava em `os_producao` e o JSON que a RPC
 * `producao_resumo(de, ate)` devolve (ver supabase/migrations/0016_producao.sql).
 */

/** Categoria derivada do motivo da OS no SGP (worker: relatorios/producao_os.py). */
export type CategoriaOS =
  | 'instalacao'
  | 'remocao'
  | 'mudanca'
  | 'corretiva'
  | 'rompimento'
  | 'servico'
  | 'outros'

/** Contagem por categoria — a mesma forma no total, no dia e na hora. */
export interface ContagemPorCategoria {
  total: number
  instalacoes: number
  remocoes: number
  mudancas: number
  corretivas: number
  rompimentos: number
  servicos: number
  outros: number
}

export interface ProducaoPeriodo {
  de: string
  ate: string
  dias: number
}

export interface ProducaoTotais extends ContagemPorCategoria {
  equipes: number
  pops: number
  /** dias do período em que houve pelo menos uma OS (base da média/dia) */
  dias_com_os: number
  /** média de dias entre a abertura e a finalização */
  espera_media: number | null
  /** OS sem hora de finalização — ficam de fora do gráfico por hora */
  sem_hora: number
}

/** Mesma janela de tamanho, imediatamente anterior — base do comparativo. */
export interface ProducaoAnterior {
  total: number
  instalacoes: number
  remocoes: number
  de: string
  ate: string
}

export interface ProducaoDia extends ContagemPorCategoria {
  dia: string
}

export interface ProducaoHora extends ContagemPorCategoria {
  hora: number
}

export interface ProducaoCategoria {
  categoria: CategoriaOS
  total: number
}

export interface ProducaoPop extends ContagemPorCategoria {
  pop: string
  pop_num: number | null
}

export interface ProducaoEquipe {
  equipe: string
  total: number
  instalacoes: number
  remocoes: number
  mudancas: number
  corretivas: number
  rompimentos: number
}

export interface ProducaoMotivo {
  motivo: string
  categoria: CategoriaOS
  total: number
}

/** Última passada BEM-SUCEDIDA do worker — vira o "atualizado às …". */
export interface ProducaoSync {
  criado_em: string
  origem: 'agenda' | 'manual' | 'backfill'
  de: string
  ate: string
  total: number
  gravados: number
  ok: boolean
  erro: string | null
}

/** Falha ainda não superada (mais recente que a última passada boa). */
export interface ProducaoFalha {
  criado_em: string
  origem: 'agenda' | 'manual' | 'backfill'
  de: string
  ate: string
  erro: string | null
}

export interface ProducaoResumo {
  periodo: ProducaoPeriodo
  totais: ProducaoTotais
  anterior: ProducaoAnterior
  por_dia: ProducaoDia[]
  por_hora: ProducaoHora[]
  por_categoria: ProducaoCategoria[]
  por_pop: ProducaoPop[]
  por_equipe: ProducaoEquipe[]
  por_motivo: ProducaoMotivo[]
  ultima_sync: ProducaoSync | null
  ultima_falha: ProducaoFalha | null
}

// ── Formas que os componentes de gráfico consomem ─────────────────────
// (ficam aqui e não no .vue porque `<script setup>` não pode exportar tipos)

/** Uma coluna do gráfico de fluxo (uma hora do dia ou um dia do mês). */
export interface PontoColuna {
  chave: string
  /** rótulo curto do eixo X */
  eixo: string
  /** título do tooltip */
  titulo: string
  sub?: string
  /** valor por categoria (chave = CategoriaOS) */
  valores: Record<string, number>
  total: number
  /** desenha mais fraco (ex.: fim de semana) */
  atenuado?: boolean
}

/** Uma linha do gráfico de barras horizontais (um POP, uma equipe, uma categoria). */
export interface LinhaBarra {
  chave: string
  rotulo: string
  /** quebra em texto, ex.: "87 instalações · 30 remoções" */
  sub?: string
  valores: Record<string, number>
  total: number
}

/** Uma OS finalizada (linha da tabela de detalhe). */
export interface OsProducao {
  os_id: number
  cliente: string | null
  contrato: number | null
  contrato_status: string | null
  motivo: string
  categoria: CategoriaOS
  subcategoria: string | null
  pop: string | null
  pop_num: number | null
  equipe: string | null
  usuario_finalizacao: string | null
  data_finalizacao: string
  hora_finalizacao: string | null
  espera_dias: number | null
}
