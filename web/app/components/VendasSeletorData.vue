<script setup lang="ts">
import { CalendarDate, getLocalTimeZone, parseDate, today } from '@internationalized/date'

// Seleção de data do "Verificar Vendas". Escreve em dois valores que o worker
// entende: `data` ('yyyy-mm-dd') e `todas` (bool → ignora a data e puxa tudo).
const props = defineProps<{ data: string, todas: boolean }>()
const emit = defineEmits<{
  'update:data': [value: string]
  'update:todas': [value: boolean]
}>()

const hoje = today(getLocalTimeZone())
const ontem = hoje.subtract({ days: 1 })

// abre já com "hoje" quando não veio nada preenchido
onMounted(() => {
  if (!props.todas && !props.data) emit('update:data', hoje.toString())
})

// ponte entre o UCalendar (CalendarDate) e o `data` string do modelo
const valor = computed<CalendarDate>({
  get() {
    try {
      return props.data ? (parseDate(props.data) as CalendarDate) : hoje
    }
    catch {
      return hoje
    }
  },
  set(cd) {
    emit('update:todas', false)
    emit('update:data', cd.toString())
  },
})

const ehHoje = computed(() => !props.todas && props.data === hoje.toString())
const ehOntem = computed(() => !props.todas && props.data === ontem.toString())

function irPara(cd: CalendarDate) {
  emit('update:todas', false)
  emit('update:data', cd.toString())
}
function verTodas() {
  emit('update:todas', true)
}

const resumo = computed(() => {
  if (props.todas) return 'todas as vendas, de qualquer data'
  const base = props.data || hoje.toString()
  const d = new Date(`${base}T00:00:00`)
  const fmt = d.toLocaleDateString('pt-BR', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })
  return `as vendas de ${fmt}`
})
</script>

<template>
  <div class="space-y-3">
    <p class="text-xs font-semibold uppercase tracking-wider text-muted">Período das vendas</p>

    <!-- atalhos: substituem o antigo dropdown/checkbox -->
    <div class="flex flex-wrap gap-2">
      <UButton
        icon="i-lucide-calendar-check"
        label="Hoje"
        :color="ehHoje ? 'primary' : 'neutral'"
        :variant="ehHoje ? 'solid' : 'subtle'"
        @click="irPara(hoje)"
      />
      <UButton
        icon="i-lucide-history"
        label="Ontem"
        :color="ehOntem ? 'primary' : 'neutral'"
        :variant="ehOntem ? 'solid' : 'subtle'"
        @click="irPara(ontem)"
      />
      <UButton
        icon="i-lucide-infinity"
        label="Todas as datas"
        :color="todas ? 'primary' : 'neutral'"
        :variant="todas ? 'solid' : 'subtle'"
        @click="verTodas"
      />
    </div>

    <!-- calendário: escolher um dia específico (some no futuro). Ao clicar num dia,
         sai do modo "todas" automaticamente. Fica esmaecido enquanto "todas" está ativo. -->
    <div
      class="w-fit rounded-xl border border-default bg-elevated/30 p-2 transition-opacity"
      :class="{ 'opacity-50': todas }"
    >
      <UCalendar v-model="valor" :max-value="hoje" color="primary" />
    </div>

    <p class="flex items-center gap-2 text-sm">
      <UIcon name="i-lucide-eye" class="size-4 shrink-0 text-primary" />
      <span class="text-muted">Puxando <span class="font-medium text-highlighted">{{ resumo }}</span>.</span>
    </p>
  </div>
</template>
