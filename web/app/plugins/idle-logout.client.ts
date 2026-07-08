// Logout automático por INATIVIDADE: 1 hora sem interação -> desloga.
//
// Detalhes de robustez:
//  • A "última atividade" fica no localStorage, compartilhada entre abas —
//    assim uma aba ociosa NÃO desloga enquanto a pessoa está ativa em outra.
//  • O relógio só reinicia em atividade REAL do usuário e em login novo
//    (SIGNED_IN). NÃO reinicia no auto-refresh do token (TOKEN_REFRESHED),
//    senão a sessão nunca expiraria por inatividade.
//  • Client-only (.client.ts): usa window/document/localStorage com segurança.
export default defineNuxtPlugin(() => {
  const IDLE_MS = 60 * 60 * 1000 // 1 hora
  const CHECK_MS = 60 * 1000 // verifica a cada 1 min
  const WRITE_THROTTLE_MS = 5 * 1000 // grava no máx. 1x/5s
  const KEY = 'giga:last-activity'

  const user = useSupabaseUser()
  const supabase = useSupabaseClient()

  let ultimaGravacao = 0
  let deslogando = false
  let uidAnterior: string | null = user.value?.id ?? null

  function setAtividade(ts = Date.now()) {
    try { localStorage.setItem(KEY, String(ts)) } catch {}
  }
  function getAtividade(): number {
    try {
      const v = localStorage.getItem(KEY)
      return v ? Number(v) : 0
    } catch {
      return 0
    }
  }
  function limparAtividade() {
    try { localStorage.removeItem(KEY) } catch {}
  }

  function marcarAtividade() {
    const t = Date.now()
    if (t - ultimaGravacao < WRITE_THROTTLE_MS) return
    ultimaGravacao = t
    setAtividade(t)
  }

  async function deslogar() {
    if (deslogando) return
    deslogando = true
    limparAtividade()
    try {
      await supabase.auth.signOut({ scope: 'local' }) // só esta sessão/dispositivo
    } catch {}
    await navigateTo('/login?motivo=inatividade', { replace: true })
    deslogando = false
  }

  function verificar() {
    if (!user.value || deslogando) return
    const ult = getAtividade()
    if (ult && Date.now() - ult >= IDLE_MS) deslogar()
  }

  // Inicializa o relógio só se ainda não houver marca (usuário já logado quando
  // o recurso subiu). Se já houver marca (ex.: aba reaberta após muito tempo),
  // deixamos a verificação decidir — pode deslogar na hora.
  if (user.value && !getAtividade()) setAtividade()

  // ATENÇÃO: no auth-js, 'SIGNED_IN' NÃO significa só "login novo" — ele também
  // dispara ao trazer a aba para o foco e ao restaurar a sessão (recover), e é
  // retransmitido entre abas. Se resetássemos em todo 'SIGNED_IN', só olhar a
  // aba já zeraria o contador e o logout de 1h nunca aconteceria.
  // Por isso: só reiniciamos o relógio quando o USUÁRIO realmente muda
  // (null -> usuário, ou troca de conta). 'INITIAL_SESSION' (reload) apenas
  // verifica se a marca preservada já venceu. 'TOKEN_REFRESHED' é ignorado.
  supabase.auth.onAuthStateChange((event, session) => {
    const uid = session?.user?.id ?? null
    if (event === 'SIGNED_OUT') {
      uidAnterior = null
      limparAtividade()
      return
    }
    if (event === 'SIGNED_IN') {
      if (uid && uid !== uidAnterior) setAtividade() // login real / troca de conta
      uidAnterior = uid
      return
    }
    if (event === 'INITIAL_SESSION' && uid) {
      uidAnterior = uid
      if (!getAtividade()) setAtividade() // 1º uso: começa o relógio
      else verificar() // reload: marca preservada -> desloga já se venceu
    }
  })

  const eventos = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'click', 'wheel']
  for (const e of eventos) {
    window.addEventListener(e, marcarAtividade, { passive: true })
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') verificar()
  })

  window.setInterval(verificar, CHECK_MS)
})
