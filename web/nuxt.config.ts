// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-06-01',
  devtools: { enabled: true },

  modules: ['@nuxtjs/supabase', '@nuxt/ui'],

  css: ['~/assets/css/main.css'],

  // branco + azul: começa no tema claro (toggle continua disponível)
  colorMode: {
    preference: 'light',
    fallback: 'light',
  },

  // @nuxtjs/supabase: usa SUPABASE_URL + SUPABASE_KEY (anon) do .env.
  // Redireciona automaticamente quem não está logado para /login.
  supabase: {
    redirectOptions: {
      login: '/login',
      callback: '/confirm',
      // rotas públicas (sem exigir login)
      exclude: ['/login', '/confirm'],
    },
  },

  runtimeConfig: {
    // ── server-only (nunca vão pro browser) ──────────────────
    giganetWebhookSecret: process.env.GIGANET_WEBHOOK_SECRET,
    n8nPublicarUrl: process.env.N8N_PUBLICAR_URL,
    n8nRegerarUrl: process.env.N8N_REGERAR_URL,
    anthropicApiKey: process.env.ANTHROPIC_API_KEY,
    anthropicModel: process.env.ANTHROPIC_MODEL || 'claude-sonnet-4-6',
    // URL interna do serviço Python do Monitor SmartOLT. As rotas
    // server/api/monitor/* fazem proxy pra cá (exigindo admin/supervisor);
    // o navegador nunca fala direto com este serviço.
    monitorApiUrl: process.env.MONITOR_API_URL || 'http://127.0.0.1:5001',
    // Segredo compartilhado com o serviço do monitor (opcional; só quando ele
    // roda em outro host e é alcançado pela rede). Vazio = sem token.
    monitorApiToken: process.env.MONITOR_API_TOKEN || '',
    public: {
      // URL do servidor Flask Aut-SGP (uso legado / health-check opcional)
      sgpUrl: '',
    },
  },

  app: {
    head: {
      title: 'Central Giganet',
      htmlAttrs: { lang: 'pt-BR' },
      meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
      link: [
        { rel: 'icon', type: 'image/png', href: '/boneco-cabeca.png' },
        { rel: 'apple-touch-icon', href: '/boneco-cabeca.png' },
      ],
    },
  },
})
