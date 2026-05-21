<!--
  传输任务卡片 - 显示单个任务的详细信息、进度条和操作按钮。
-->
<template>
  <div class="transfer-card">
    <div class="card-header">
      <div class="task-info">
        <el-tag :type="task.type === 'upload' ? 'primary' : 'success'" size="small">
          {{ task.type === 'upload' ? '上传' : task.type === 'download' ? '下载' : task.type === 'copy' ? '复制' : '移动' }}
        </el-tag>
        <span class="file-name">{{ task.file_name }}</span>
      </div>
      <el-tag :type="statusTagType" size="small">{{ statusLabel }}</el-tag>
    </div>

    <div class="card-body">
      <div class="path-row">
        <span class="label">源:</span><span>{{ task.source_path }}</span>
      </div>
      <div class="path-row">
        <span class="label">目标:</span><span>{{ task.target_path }}</span>
      </div>
      <div v-if="task.file_size" class="size-row">
        {{ formatSize(task.transferred) }} / {{ formatSize(task.file_size) }}
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
      <el-icon><WarningFilled /></el-icon> {{ task.error_message }}
    </div>

    <div class="card-actions">
      <el-button v-if="['queued', 'pending', 'running'].includes(task.status)" size="small" @click="$emit('pause', task.id)">
        <el-icon><VideoPause /></el-icon>暂停
      </el-button>
      <el-button v-if="task.status === 'paused'" type="primary" size="small" @click="$emit('resume', task.id)">
        <el-icon><VideoPlay /></el-icon>继续
      </el-button>
      <el-button v-if="task.status === 'failed'" type="warning" size="small" @click="$emit('retry', task.id)">
        <el-icon><RefreshRight /></el-icon>重试
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
</script>

<style scoped>
.transfer-card {
  background: var(--card-bg); border: 1px solid var(--border-color);
  border-radius: 10px; padding: 16px; display: flex; flex-direction: column; gap: 10px;
}
.card-header { display: flex; justify-content: space-between; align-items: center; }
.task-info { display: flex; align-items: center; gap: 8px; }
.file-name { font-weight: 600; font-size: 14px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-body { display: flex; flex-direction: column; gap: 4px; }
.path-row { display: flex; gap: 6px; font-size: 12px; color: var(--text-secondary); }
.path-row .label { min-width: 32px; }
.size-row { font-size: 12px; color: var(--text-regular); }
.error-msg { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--danger-color); background: #fef0f0; padding: 6px 10px; border-radius: 6px; }
.card-actions { display: flex; gap: 8px; justify-content: flex-end; }
</style>
