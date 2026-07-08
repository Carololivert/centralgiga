// Regras de senha para o checklist ao vivo nas telas de senha.
// (A validação que vale para segurança é a do servidor — server/utils/senha.ts.)

export interface RegraSenha {
  label: string
  ok: boolean
}

export function regrasSenha(senha: string): RegraSenha[] {
  return [
    { label: 'Mínimo 8 caracteres', ok: senha.length >= 8 },
    { label: 'Uma letra maiúscula (A-Z)', ok: /[A-Z]/.test(senha) },
    { label: 'Uma letra minúscula (a-z)', ok: /[a-z]/.test(senha) },
    { label: 'Um número (0-9)', ok: /[0-9]/.test(senha) },
    { label: 'Um símbolo (!@#$…)', ok: /[^A-Za-z0-9]/.test(senha) },
  ]
}

export function senhaValida(senha: string): boolean {
  return regrasSenha(senha).every(r => r.ok)
}
