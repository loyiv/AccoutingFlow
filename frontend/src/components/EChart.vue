<template>
  <div ref="el" class="chart" :style="{ height: `${heightPx}px` }"></div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  option: any
  height?: number
}>()

const heightPx = computed(() => props.height ?? 320)

const el = ref<HTMLDivElement | null>(null)
let inst: echarts.ECharts | null = null
let ro: ResizeObserver | null = null

function render() {
  if (!inst) return
  inst.setOption(props.option || {}, { notMerge: true, lazyUpdate: true })
}

onMounted(() => {
  if (!el.value) return
  inst = echarts.init(el.value)
  render()
  ro = new ResizeObserver(() => inst?.resize())
  ro.observe(el.value)
})

watch(
  () => props.option,
  () => render(),
  { deep: true },
)

onBeforeUnmount(() => {
  ro?.disconnect()
  ro = null
  inst?.dispose()
  inst = null
})
</script>

<style scoped>
.chart {
  width: 100%;
}
</style>


