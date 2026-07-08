// Validação de força de senha + geração de senha provisória.
// Fonte de verdade do lado do servidor (o cliente valida só para UX).

/** Retorna uma mensagem de erro se a senha for fraca, ou null se estiver ok. */
export function validarSenhaForte(senha: string): string | null {
  if (!senha || senha.length < 8) return 'A senha deve ter no mínimo 8 caracteres.'
  if (!/[A-Z]/.test(senha)) return 'A senha deve conter ao menos uma letra maiúscula.'
  if (!/[a-z]/.test(senha)) return 'A senha deve conter ao menos uma letra minúscula.'
  if (!/[0-9]/.test(senha)) return 'A senha deve conter ao menos um número.'
  if (!/[^A-Za-z0-9]/.test(senha)) return 'A senha deve conter ao menos um símbolo (!@#$…).'
  return null
}

/**
 * Gera uma senha provisória forte e legível (evita caracteres ambíguos
 * como O/0, l/1/I). Garante ao menos 1 de cada classe exigida.
 */
export function gerarSenhaProvisoria(tamanho = 14): string {
  const mai = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
  const min = 'abcdefghijkmnpqrstuvwxyz'
  const num = '23456789'
  const sim = '!@#$%&*?'
  const todos = mai + min + num + sim

  const rnd = (n: number) => {
    const a = new Uint32Array(1)
    globalThis.crypto.getRandomValues(a)
    return a[0]! % n
  }

  const chars: string[] = [
    mai[rnd(mai.length)]!,
    min[rnd(min.length)]!,
    num[rnd(num.length)]!,
    sim[rnd(sim.length)]!,
  ]
  for (let i = chars.length; i < tamanho; i++) chars.push(todos[rnd(todos.length)]!)

  // Embaralha (Fisher–Yates) para não deixar as classes sempre no início.
  for (let i = chars.length - 1; i > 0; i--) {
    const j = rnd(i + 1)
    ;[chars[i], chars[j]] = [chars[j]!, chars[i]!]
  }
  return chars.join('')
}
