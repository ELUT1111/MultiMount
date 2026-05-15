<!--
  传输进度条 — 显示分块传输进度百分比、速度、剩余时间。
  支持: paused 状态用黄色, failed 用红色, completed 用绿色。
-->
<template>
  <div class="transfer-progress">
    <el-progress
      :percentage="percentage"
      :status="progressStatus"
      :stroke-width="8"
      :format="() => percentageText"
    />
    <div class="progress-meta">
      <span v-if="speed" class="speed">{{ formatSpeed(speed) }}</span>
      <span v-if="remainingText" class="remaining">{{ remainingText }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatSize, formatSpeed } from '@/utils/format'

const props = defineProps({
  transferred: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  speed: { type: Number, default: 0 },
  status: { type: String, default: 'running' },
})

const percentage = computed(() => {
  if (!props.total || props.total <= 0) return 0
  return Math.min(100, Math.round((props.transferred / props.total) * 100))
})

const percentageText = computed(() => `${percentage.value}%`)

const progressStatus = computed(() => {
  if (props.status === 'completed') return 'success'
  if (props.status === 'failed') return 'exception'
  if (props.status === 'paused') return 'warning'
  return ''  // 默认 (蓝色进行中)
})

const remainingText = computed(() => {
  if (!props.speed || !props.total || props.status !== 'running') return ''
  const remaining = props.total - props.transferred
  if (remaining <= 0) return ''
  const seconds = Math.ceil(remaining / props.speed)
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.ceil(seconds / 60)}分钟`
  return `${Math.ceil(seconds / 3600)}小时`
})
</script>

<style scoped>
.transfer-progress { display: flex; flex-direction: column; gap: 4px; }
.progress-meta { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-secondary); }
.speed { color: var(--primary-color); }
</style>
