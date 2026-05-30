<template>
  <div class="transfer-card" :class="[`status-${task.status}`, `type-${task.type}`]">
    <span class="status-rail" />
    <div class="card-header">
      <div class="task-info">
        <span class="type-badge">{{ task.type === 'copy' ? '复制' : '移动' }}</span>
        <div class="title-stack">
          <span class="file-name">{{ task.file_name }}</span>
          <span class="task-subtitle">{{ task.file_size ? `${formatSize(task.file_size)} · ${statusLabel}` : statusLabel }}</span>
        </div>
      </div>
      <el-tag :type="statusTagType" size="small" effect="light">{{ statusLabel }}</el-tag>
    </div>

    <div class="card-body">
      <div class="route-box">
        <div class="path-row">
          <span class="label">源</span><span>{{ task.source_path }}</span>
        </div>
        <div class="route-line" />
        <div class="path-row">
          <span class="label">目标</span><span>{{ task.target_path }}</span>
        </div>
      </div>
      <div class="progress-summary">
        <span v-if="task.file_size">{{ formatSize(task.transferred) }} / {{ formatSize(task.file_size) }}</span>
        <span v-else>等待大小信息</span>
        <strong>{{ progressPercent }}%</strong>
      </div>
    </div>

    <TransferProgress
      v-if="['queued', 'pending', 'running', 'paused'].includes(task.status)"
      :transferred="task.transferred"
      :total="task.file_size || 0"
      :speed="task.speed || 0"
      :status="task.status"
    />

    <div v-if="task.status === 'failed' && task.error_message" class="error-msg">
      <el-icon><WarningFilled /></el-icon>
      <span>{{ task.error_message }}</span>
    </div>

    <div class="card-actions">
      <el-button v-if="['queued', 'pending', 'running'].includes(task.status)" size="small" plain @click="$emit('pause', task.id)">
        <el-icon><VideoPause /></el-icon>
        暂停
      </el-button>
      <el-button v-if="task.status === 'paused'" type="primary" size="small" @click="$emit('resume', task.id)">
        <el-icon><VideoPlay /></el-icon>
        继续
      </el-button>
      <el-button v-if="task.status === 'failed'" type="warning" size="small" @click="$emit('retry', task.id)">
        <el-icon><RefreshRight /></el-icon>
        重试
      </el-button>
      <el-button
        v-if="task.status !== 'completed'"
        type="danger"
        size="small"
        plain
        @click="$emit('cancel', task.id)"
      >
        取消
      </el-button>
      <el-button v-if="task.status === 'completed'" type="danger" size="small" plain @click="$emit('cancel', task.id)">
        删除
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { VideoPause, VideoPlay, RefreshRight, WarningFilled } from '@element-plus/icons-vue'
import TransferProgress from './TransferProgress.vue'
import { formatSize } from '@/utils/format'

const props = defineProps({
  task: { type: Object, required: true },
})

defineEmits(['pause', 'resume', 'cancel', 'retry'])

const statusTagType = computed(() => ({
  queued: 'info',
  pending: 'info',
  running: '',
  paused: 'warning',
  completed: 'success',
  failed: 'danger',
}[props.task.status] || 'info'))

const statusLabel = computed(() => ({
  queued: '等待中',
  pending: '等待中',
  running: '传输中',
  paused: '已暂停',
  completed: '已完成',
  failed: '已失败',
}[props.task.status] || props.task.status))

const progressPercent = computed(() => {
  if (props.task.status === 'completed') return 100
  if (!props.task.file_size) return 0
  return Math.min(100, Math.round((props.task.transferred / props.task.file_size) * 100))
})
</script>

<style scoped>
.transfer-card {
  position: relative;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 16px 16px 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.transfer-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}
.status-rail {
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--primary-color);
}
.status-queued .status-rail,
.status-pending .status-rail { background: var(--text-secondary); }
.status-running .status-rail { background: var(--primary-color); }
.status-paused .status-rail { background: var(--warning-color); }
.status-completed .status-rail { background: var(--success-color); }
.status-failed .status-rail { background: var(--danger-color); }
.status-running { border-color: color-mix(in srgb, var(--primary-color) 28%, var(--border-color)); }
.status-completed { border-color: color-mix(in srgb, var(--success-color) 30%, var(--border-color)); }
.status-failed { border-color: color-mix(in srgb, var(--danger-color) 30%, var(--border-color)); }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.task-info { display: flex; align-items: center; gap: 10px; min-width: 0; }
.type-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: var(--success-color);
  background: color-mix(in srgb, var(--success-color) 12%, transparent);
}
.type-move .type-badge {
  color: var(--warning-color);
  background: color-mix(in srgb, var(--warning-color) 14%, transparent);
}
.title-stack { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.file-name {
  font-weight: 700;
  font-size: 14px;
  max-width: min(520px, 48vw);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-subtitle { color: var(--text-secondary); font-size: 12px; }
.card-body { display: flex; flex-direction: column; gap: 10px; }
.route-box {
  display: grid;
  gap: 5px;
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--primary-color) 4%, transparent);
}
.path-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  font-size: 12px;
  color: var(--text-secondary);
}
.path-row .label {
  color: var(--text-regular);
  font-weight: 600;
}
.path-row span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.route-line {
  width: 1px;
  height: 8px;
  margin-left: 16px;
  background: var(--border-color);
}
.progress-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 12px;
}
.progress-summary strong { color: var(--text-regular); font-size: 13px; }
.error-msg {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  color: var(--danger-color);
  background: color-mix(in srgb, var(--danger-color) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--danger-color) 24%, var(--border-color));
  padding: 8px 10px;
  border-radius: 8px;
  line-height: 1.5;
}
.error-msg span { overflow-wrap: anywhere; }
.card-actions { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }
.card-actions :deep(.el-button) { margin-left: 0; }

@media (max-width: 640px) {
  .card-header {
    flex-direction: column;
  }
  .file-name {
    max-width: 72vw;
  }
  .card-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .card-actions :deep(.el-button) {
    width: 100%;
  }
}
</style>
