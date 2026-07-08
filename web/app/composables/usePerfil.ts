import type { Perfil } from '~/types/db'

/**
 * Carrega e mantém o perfil (cargo) do usuário logado.
 * Usa useState para compartilhar entre páginas/middleware sem refetch.
 */
export function usePerfil() {
  const user = useSupabaseUser()
  const client = useSupabaseClient()
  const perfil = useState<Perfil | null>('perfil', () => null)

  async function carregar(force = false) {
    if (!user.value) {
      perfil.value = null
      return null
    }
    if (perfil.value && !force) return perfil.value

    const { data, error } = await client
      .from('profiles')
      .select('id, full_name, role, active, must_change_password')
      .eq('id', user.value.id)
      .single()

    perfil.value = error ? null : (data as Perfil)
    return perfil.value
  }

  const isAdmin = computed(() => perfil.value?.role === 'admin')

  return { perfil, isAdmin, carregar }
}
