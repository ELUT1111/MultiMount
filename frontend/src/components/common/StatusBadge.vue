<!--
  状态指示灯组件 — 显示带颜色圆点的状态标签。
  支持 online/offline/warning/connecting 四种状态。
-->
<template>
  <span class="status-badge" :class="status">
    <span class="status-dot" />
    <span class="status-label">{{ label || statusText }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: 'offline', validator: (v) => ['online', 'offline', 'warning', 'connecting'].includes(v) },
  label: { type: String, default: '' },
})

const statusText = computed(() => ({
  online: '在线',
  offline: '离线',
  warning: '警告',
  connecting: '连接中',
}[props.status]))
</script>

<style scoped>
.status-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }
.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--dot-color, #909399);
  flex-shrink: 0;
}
.status-badge.online .status-dot { background: #67c23a; box-shadow: 0 0 6px rgba(103,194,58,0.4); }
.status-badge.offline .status-dot { background: #909399; }
.status-badge.warning .status-dot { background: #e6a23c; box-shadow: 0 0 6px rgba(230,162,60,0.4); }
.status-badge.connecting .status-dot {
  background: #409eff;
  animation: pulse 1.2s ease-in-out infinite;
}
.status-label { color: var(--text-regular); }
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}
</style>
