<script setup lang="ts">
import type { EventoFibra, PonRef } from '~/types/monitor'

// Painel do Monitor de Rede — só admin/supervisor (o systems.allowed_roles
// controla o menu/dashboard; este middleware garante o acesso à rota).
definePageMeta({ middleware: 'role', roles: ['admin', 'supervisor'] })

const { snapshot, carregando, erro, iniciar, parar } = useMonitor()

// Liga o polling ao entrar na tela e desliga ao sair (não fica batendo
// no SmartOLT quando o supervisor navega para outro sistema).
onMounted(() => iniciar())
onUnmounted(() => parar())

const modalOpen = ref(false)
const ponSel = ref<PonRef | null>(null)

function abrirPon(e: EventoFibra) {
  ponSel.value = {
    olt: String(e.olt_id), board: String(e.board), port: String(e.port), regiao: e.regiao,
  }
  modalOpen.value = true
}
</script>

<template>
  <UDashboardPanel id="monitor">
    <template #header>
      <UDashboardNavbar title="Monitor de Rede" icon="i-lucide-radio-tower">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <MonitorRefreshControls />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="space-y-6">
        <UAlert
          v-if="erro && !snapshot"
          color="error"
          variant="subtle"
          icon="i-lucide-plug-zap"
          title="Sem conexão com o serviço do monitor"
          :description="`${erro}. Confira se o serviço Python (monitor/server.py) está no ar.`"
        />

        <div v-if="!snapshot && carregando" class="flex justify-center py-16 text-muted">
          <UIcon name="i-lucide-loader-circle" class="size-7 animate-spin" />
        </div>

        <template v-if="snapshot">
          <MonitorHealthBanner :health="snapshot.health" />

          <!-- OLTs: temperatura / uptime -->
          <section class="space-y-3">
            <h2 class="text-xs uppercase tracking-wide text-muted font-medium">
              OLTs — temperatura
            </h2>
            <div class="grid gap-4 grid-cols-[repeat(auto-fill,minmax(13rem,1fr))]">
              <MonitorOltCard v-for="o in snapshot.olts" :key="o.id" :olt="o" />
            </div>
          </section>

          <!-- KPIs -->
          <section class="space-y-3">
            <h2 class="text-xs uppercase tracking-wide text-muted font-medium">
              Situação agora
            </h2>
            <div class="grid gap-4 grid-cols-2 lg:grid-cols-4">
              <MonitorStatChip
                title="Parcial (LOS)"
                :value="snapshot.totais.partial_los.pons"
                :sub="`${snapshot.totais.partial_los.subs} assinantes`"
                icon="i-lucide-signal-medium"
                tone="warning"
              />
              <MonitorStatChip
                title="Total (LOS)"
                :value="snapshot.totais.los.pons"
                :sub="`${snapshot.totais.los.subs} assinantes`"
                icon="i-lucide-signal-zero"
                tone="error"
              />
              <MonitorStatChip
                title="Energia"
                :value="snapshot.totais.power.pons"
                :sub="`${snapshot.totais.power.subs} assinantes`"
                icon="i-lucide-zap"
                tone="info"
              />
              <MonitorStatChip
                title="Offline"
                :value="snapshot.totais.offline.pons"
                :sub="`${snapshot.totais.offline.subs} assinantes`"
                icon="i-lucide-power-off"
                tone="neutral"
              />
            </div>
          </section>

          <!-- Fibra -->
          <UPageCard
            title="Fibra — PONs afetadas"
            description="Clique numa linha para cruzar com o SGP e ver os clientes."
            icon="i-lucide-spline"
            variant="subtle"
            :ui="{ body: 'px-0 sm:px-0' }"
          >
            <MonitorFibraTable :eventos="snapshot.eventos_fibra" @open="abrirPon" />
          </UPageCard>

          <!-- Energia -->
          <UPageCard
            title="Energia / Offline"
            description="Agrupado por zona (energia segue a geografia, não a topologia óptica)."
            icon="i-lucide-zap"
            variant="subtle"
            :ui="{ body: 'px-0 sm:px-0' }"
          >
            <MonitorEnergiaTable :eventos="snapshot.eventos_energia" />
          </UPageCard>
        </template>
      </div>

      <MonitorPonModal v-model:open="modalOpen" :pon="ponSel" />
    </template>
  </UDashboardPanel>
</template>
