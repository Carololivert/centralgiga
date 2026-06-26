import type { Role } from '~/types/db'

/**
 * Middleware de cargo. Use em páginas com:
 *   definePageMeta({ middleware: 'role', roles: ['admin'] })
 *
 * Sem `roles`, apenas exige login + perfil ativo.
 * (O redirect de "não logado → /login" já é feito pelo @nuxtjs/supabase.)
 */
export default defineNuxtRouteMiddleware(async (to) => {
  const { perfil, carregar } = usePerfil()
  if (!perfil.value) await carregar()

  if (!perfil.value || perfil.value.active === false) {
    return navigateTo('/login')
  }

  const required = to.meta.roles as Role[] | undefined
  if (required && required.length && !required.includes(perfil.value.role)) {
    throw createError({
      statusCode: 403,
      statusMessage: 'Você não tem permissão para acessar esta página.',
    })
  }
})
