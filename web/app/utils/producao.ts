import type { CategoriaOS, ContagemPorCategoria, OsProducao } from '~/types/producao'

/**
 * Vocabulário do dashboard de Produção: rótulo, cor e chave de contagem de
 * cada categoria — em UM lugar só, para gráfico, legenda e tabela nunca
 * discordarem.
 *
 * A ORDEM é fixa e nunca cicla: cada categoria carrega o seu slot de cor do
 * início ao fim (definidos em assets/css/main.css, validados nos dois temas).
 * Filtrar o período não repinta ninguém.
 */
export interface DefCategoria {
  chave: CategoriaOS
  rotulo: string
  /** rótulo curto para caber em legenda/eixo apertado */
  curto: string
  /** var() do CSS — a mesma cor no tema claro e no escuro */
  cor: string
  /** campo correspondente nos objetos de contagem */
  campo: keyof ContagemPorCategoria
  icone: string
}

export const CATEGORIAS: DefCategoria[] = [
  { chave: 'instalacao', rotulo: 'Instalações', curto: 'Instalação', cor: 'var(--viz-instalacao)', campo: 'instalacoes', icone: 'i-lucide-plug-zap' },
  { chave: 'remocao', rotulo: 'Remoções', curto: 'Remoção', cor: 'var(--viz-remocao)', campo: 'remocoes', icone: 'i-lucide-package-minus' },
  { chave: 'mudanca', rotulo: 'Mudanças de endereço', curto: 'Mudança', cor: 'var(--viz-mudanca)', campo: 'mudancas', icone: 'i-lucide-truck' },
  { chave: 'corretiva', rotulo: 'Corretivas', curto: 'Corretiva', cor: 'var(--viz-corretiva)', campo: 'corretivas', icone: 'i-lucide-wrench' },
  { chave: 'rompimento', rotulo: 'Rompimentos de fibra', curto: 'Rompimento', cor: 'var(--viz-rompimento)', campo: 'rompimentos', icone: 'i-lucide-unlink' },
  { chave: 'servico', rotulo: 'Serviços e entregas', curto: 'Serviço', cor: 'var(--viz-servico)', campo: 'servicos', icone: 'i-lucide-hand-helping' },
  { chave: 'outros', rotulo: 'Outros', curto: 'Outros', cor: 'var(--viz-outros)', campo: 'outros', icone: 'i-lucide-circle-dashed' },
]

const PORA_CHAVE = new Map(CATEGORIAS.map(c => [c.chave, c]))

export function categoria(chave: CategoriaOS | string | null | undefined): DefCategoria {
  return PORA_CHAVE.get(chave as CategoriaOS) ?? CATEGORIAS[CATEGORIAS.length - 1]!
}

export function corCategoria(chave: CategoriaOS | string | null | undefined): string {
  return categoria(chave).cor
}

export function rotuloCategoria(chave: CategoriaOS | string | null | undefined): string {
  return categoria(chave).curto
}

/** Subcategoria crua do worker → texto para a tabela. */
const SUBCATEGORIAS: Record<string, string> = {
  casa: 'casa',
  condominio: 'condomínio',
  predio: 'prédio',
  contrato: 'local do contrato',
  diverso: 'local diverso',
}

export function rotuloSubcategoria(sub: string | null | undefined): string {
  if (!sub) return ''
  return SUBCATEGORIAS[sub] ?? sub
}

// ── Datas ──────────────────────────────────────────────────────────────
// Tudo que vem do banco é 'yyyy-mm-dd' puro. Passar isso pelo `new Date()`
// faria o JS interpretar como UTC e mostrar o dia ANTERIOR no fuso -03 —
// por isso as funções abaixo fatiam a string em vez de criar Date.

export function diaCurto(iso: string): string {
  const [, mes, dia] = iso.split('-')
  return `${dia}/${mes}`
}

export function diaLongo(iso: string): string {
  const [ano, mes, dia] = iso.split('-')
  return `${dia}/${mes}/${ano}`
}

const DIAS_SEMANA = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb']

export function diaDaSemana(iso: string): string {
  const [ano, mes, dia] = iso.split('-').map(Number)
  return DIAS_SEMANA[new Date(ano!, mes! - 1, dia!).getDay()] ?? ''
}

export function ehFimDeSemana(iso: string): boolean {
  const [ano, mes, dia] = iso.split('-').map(Number)
  const d = new Date(ano!, mes! - 1, dia!).getDay()
  return d === 0 || d === 6
}

/** 'yyyy-mm-dd' de uma data local (sem passar por UTC). */
export function paraISO(d: Date): string {
  return d.toLocaleDateString('en-CA')
}

export function hojeISO(): string {
  return paraISO(new Date())
}

export function somarDias(iso: string, dias: number): string {
  const [ano, mes, dia] = iso.split('-').map(Number)
  const d = new Date(ano!, mes! - 1, dia! + dias)
  return paraISO(d)
}

/** Primeiro e último dia do mês de `iso` (ou de N meses atrás). */
export function limitesDoMes(iso: string, deslocamento = 0): { de: string, ate: string } {
  const [ano, mes] = iso.split('-').map(Number)
  const primeiro = new Date(ano!, mes! - 1 + deslocamento, 1)
  const ultimo = new Date(ano!, mes! + deslocamento, 0)
  return { de: paraISO(primeiro), ate: paraISO(ultimo) }
}

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

export function nomeDoMes(iso: string): string {
  const [ano, mes] = iso.split('-').map(Number)
  return `${MESES[mes! - 1]} de ${ano}`
}

export function hora2(h: number): string {
  return `${String(h).padStart(2, '0')}h`
}

/** '17:22:08' → '17:22' */
export function horaCurta(hora: string | null | undefined): string {
  return (hora ?? '').slice(0, 5)
}

// ── Números ────────────────────────────────────────────────────────────

export function numero(v: number | null | undefined): string {
  return (v ?? 0).toLocaleString('pt-BR')
}

/** Variação percentual contra o período anterior. null quando não dá pra comparar. */
export function variacao(atual: number, anterior: number): number | null {
  if (!anterior) return null
  return ((atual - anterior) / anterior) * 100
}

export function textoVariacao(v: number | null): string {
  if (v === null) return ''
  const sinal = v > 0 ? '+' : ''
  return `${sinal}${v.toFixed(0)}%`
}

// ── Exportação ─────────────────────────────────────────────────────────

const COLUNAS_CSV: { campo: keyof OsProducao, titulo: string }[] = [
  { campo: 'os_id', titulo: 'OS' },
  { campo: 'data_finalizacao', titulo: 'Data' },
  { campo: 'hora_finalizacao', titulo: 'Hora' },
  { campo: 'categoria', titulo: 'Categoria' },
  { campo: 'motivo', titulo: 'Motivo' },
  { campo: 'pop', titulo: 'POP' },
  { campo: 'equipe', titulo: 'Equipe' },
  { campo: 'cliente', titulo: 'Cliente' },
  { campo: 'contrato', titulo: 'Contrato' },
  { campo: 'contrato_status', titulo: 'Status do contrato' },
  { campo: 'usuario_finalizacao', titulo: 'Finalizou' },
  { campo: 'espera_dias', titulo: 'Dias de espera' },
]

function celulaCSV(valor: unknown): string {
  const texto = valor === null || valor === undefined ? '' : String(valor)
  return /[";\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto
}

/**
 * CSV das OS na tela. Separador `;` e BOM: é o que o Excel em pt-BR abre com
 * as colunas certas e sem quebrar acento.
 */
export function csvDasOS(linhas: OsProducao[]): string {
  const cabecalho = COLUNAS_CSV.map(c => c.titulo).join(';')
  const corpo = linhas.map(l =>
    COLUNAS_CSV.map(c => celulaCSV(c.campo === 'categoria'
      ? rotuloCategoria(l.categoria)
      : l[c.campo])).join(';'),
  )
  return `﻿${[cabecalho, ...corpo].join('\r\n')}`
}

export function baixarTexto(nome: string, conteudo: string, tipo = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([conteudo], { type: tipo }))
  const a = document.createElement('a')
  a.href = url
  a.download = nome
  // A âncora precisa estar NO documento (Firefox ignora click() em elemento
  // solto) e a URL só pode ser revogada depois que o navegador começou a
  // baixar — revogar no mesmo tick cancela downloads grandes.
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    a.remove()
    URL.revokeObjectURL(url)
  }, 1000)
}
