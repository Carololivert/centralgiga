import type { CategoriaOS, OsProducao, ProducaoResumo } from '~/types/producao'

/**
 * A tabela de detalhe é buscada em PÁGINAS de 1000 com `.range()`.
 *
 * Um `.limit(3000)` seco não funcionaria: o PostgREST aplica `min(limit,
 * max-rows)` e corta em silêncio — sem erro e sem sinal na resposta — então o
 * aviso de "lista cortada" nunca apareceria e a tela mostraria menos OS do que
 * os gráficos, sem explicar por quê. Com `range` nós é que controlamos o corte.
 */
const PAGINA_DETALHE = 1000
const LIMITE_DETALHE = 5000

/**
 * Dados do dashboard de Produção.
 *
 * Duas leituras, de propósito:
 *  • `resumo` — RPC `producao_resumo`, que agrega no banco. Um mês tem ~1.200
 *    OS; somar isso no Postgres e trazer só os totais deixa a tela instantânea.
 *  • `detalhe` — as linhas de `os_producao` da tabela "OS finalizadas", filtradas
 *    por categoria (por padrão instalações e remoções, que é o pedido do dia).
 *
 * A RLS (0016) já restringe as duas leituras a admin/supervisor.
 */
export function useProducao() {
  const client = useSupabaseClient()

  const de = ref('')
  const ate = ref('')

  const resumo = ref<ProducaoResumo | null>(null)
  const carregando = ref(false)
  const erro = ref<string | null>(null)

  /** meses que já têm produção carregada — alimenta o seletor "relatório mensal" */
  const meses = ref<{ mes: string, total: number }[]>([])

  const detalhe = ref<OsProducao[]>([])
  const carregandoDetalhe = ref(false)
  const detalheTruncado = ref(false)
  const categoriasDetalhe = ref<CategoriaOS[]>(['instalacao', 'remocao'])

  async function carregarResumo() {
    if (!de.value || !ate.value) return
    carregando.value = true
    erro.value = null
    const { data, error } = await client.rpc('producao_resumo', {
      p_de: de.value,
      p_ate: ate.value,
    } as never)
    carregando.value = false

    if (error) {
      erro.value = error.message
      return
    }
    resumo.value = data as unknown as ProducaoResumo
  }

  async function carregarDetalhe() {
    if (!de.value || !ate.value) return
    carregandoDetalhe.value = true

    const acumulado: OsProducao[] = []
    let cortou = false

    for (let inicio = 0; inicio < LIMITE_DETALHE; inicio += PAGINA_DETALHE) {
      let q = client
        .from('os_producao')
        .select('os_id, cliente, contrato, contrato_status, motivo, categoria, subcategoria,'
          + ' pop, pop_num, equipe, usuario_finalizacao, data_finalizacao, hora_finalizacao, espera_dias')
        .gte('data_finalizacao', de.value)
        .lte('data_finalizacao', ate.value)

      // lista vazia = "todas as categorias" (o .in() com [] não devolveria nada)
      if (categoriasDetalhe.value.length) {
        q = q.in('categoria', categoriasDetalhe.value)
      }

      const { data, error } = await q
        .order('data_finalizacao', { ascending: false })
        .order('hora_finalizacao', { ascending: false, nullsFirst: false })
        .order('os_id', { ascending: false }) // desempate estável: sem ele, duas OS
        .range(inicio, inicio + PAGINA_DETALHE - 1) // na mesma hora podiam repetir/sumir entre páginas

      if (error) {
        carregandoDetalhe.value = false
        erro.value = error.message
        return
      }

      const pagina = (data ?? []) as unknown as OsProducao[]
      acumulado.push(...pagina)
      if (pagina.length < PAGINA_DETALHE) break
      if (acumulado.length >= LIMITE_DETALHE) cortou = true
    }

    carregandoDetalhe.value = false
    detalhe.value = acumulado
    detalheTruncado.value = cortou
  }

  async function carregarMeses() {
    const { data } = await client.rpc('producao_meses' as never)
    meses.value = (data ?? []) as unknown as { mes: string, total: number }[]
  }

  async function carregar() {
    await Promise.all([carregarResumo(), carregarDetalhe(), carregarMeses()])
  }

  function definirPeriodo(novoDe: string, novoAte: string) {
    de.value = novoDe <= novoAte ? novoDe : novoAte
    ate.value = novoDe <= novoAte ? novoAte : novoDe
  }

  return {
    de,
    ate,
    resumo,
    meses,
    carregando,
    erro,
    detalhe,
    detalheTruncado,
    carregandoDetalhe,
    categoriasDetalhe,
    limiteDetalhe: LIMITE_DETALHE,
    carregar,
    carregarResumo,
    carregarDetalhe,
    definirPeriodo,
  }
}
