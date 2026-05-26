<template>
  <div class="transfer-tasks">
    <div class="page-header">
      <h2>传输任务</h2>
      <div class="header-actions">
        <el-button @click="transfers.fetchTasks()" :icon="Refresh">刷新</el-button>
        <el-button @click="handleBatchPause" :disabled="!transfers.activeCount">全部暂停</el-button>
        <el-button type="primary" @click="handleBatchResume">全部继续</el-button>
        <el-button type="danger" plain @click="handleBatchCancel" :disabled="!runningCount">全部取消</el-button>
        <el-button @click="handleClearCompleted" :disabled="!completedCount">清除已完成</el-button>
      </div>
    </div>

    <el-tabs v-model="transfers.activeTab">
      <el-tab-pane name="running">
        <template #label>
          进行中 <el-badge :value="runningCount" v-if="runningCount" :max="99" />
        </template>
      </el-tab-pane>
      <el-tab-pane name="completed">
        <template #label>
          已完成 <el-badge :value="completedCount" v-if="completedCount" :max="99" type="success" />
        </template>
      </el-tab-pane>
      <el-tab-pane name="failed">
        <template #label>
          已失败 <el-badge :value="failedCount" v-if="failedCount" :max="99" type="danger" />
        </template>
      </el-tab-pane>
    </el-tabs>

    <div v-loading="transfers.loading" class="task-list">
      <el-empty v-if="!transfers.loading && transfers.filteredTasks.length === 0" description="暂无复制/移动任务" />

      <TransferCard
        v-for="task in transfers.filteredTasks"
        :key="task.id"
        :task="task"
        @pause="transfers.pauseTask"
        @resume="transfers.resumeTask"
        @cancel="handleCancel"
        @retry="transfers.retryTask"
      />
    </div>

    <div class="transfer-footer">
      <div class="stat">
        <el-icon><Connection /></el-icon>
        <span>传输速度: {{ formatSpeed(transfers.totalTransferSpeed) }}</span>
      </div>
      <div class="stat">
        <el-icon><Connection /></el-icon>
        <span>并发任务: {{ transfers.activeCount }}</span>
      </div>
      <div class="stat ws-status">
        <span class="ws-dot" :class="wsConnected ? 'connected' : 'disconnected'" />
        <span>{{ wsConnected ? '实时同步' : '未连接' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { Connection, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTransfersStore } from '@/stores/transfers'
import { buildWebSocketUrl, useWebSocket } from '@/composables/useWebSocket'
import { formatSpeed } from '@/utils/format'
import TransferCard from '@/components/transfer/TransferCard.vue'

const transfers = useTransfersStore()

const { data: wsData, connected: wsConnected, connect: wsConnect } = useWebSocket(
  buildWebSocketUrl('/api/v1/transfers/ws'),
)

const activeStatuses = ['queued', 'pending', 'running', 'paused']
const runningCount = computed(() => transfers.tasks.filter((t) => activeStatuses.includes(t.status)).length)
const completedCount = computed(() => transfers.tasks.filter((t) => t.status === 'completed').length)
const failedCount = computed(() => transfers.tasks.filter((t) => t.status === 'failed').length)

watch(wsData, (val) => {
  if (val?.type === 'transfer_progress') {
    transfers.updateTaskProgress(val)
  }
})

async function handleCancel(id) {
  await ElMessageBox.confirm('确定取消此任务？', '确认', { type: 'warning' })
  await transfers.cancelTask(id)
  ElMessage.success('已取消')
}

async function handleBatchPause() {
  const running = transfers.tasks.filter((t) => t.status === 'running')
  await Promise.allSettled(running.map((t) => transfers.pauseTask(t.id)))
  ElMessage.success('已全部暂停')
}

async function handleBatchResume() {
  const paused = transfers.tasks.filter((t) => t.status === 'paused')
  await Promise.allSettled(paused.map((t) => transfers.resumeTask(t.id)))
  ElMessage.success('已全部恢复')
}

async function handleBatchCancel() {
  await ElMessageBox.confirm('确定取消所有进行中的任务？', '确认', { type: 'warning' })
  const active = transfers.tasks.filter((t) => activeStatuses.includes(t.status))
  await Promise.allSettled(active.map((t) => transfers.cancelTask(t.id)))
  ElMessage.success('已全部取消')
}

async function handleClearCompleted() {
  await ElMessageBox.confirm('确定清除所有已完成的任务？', '确认', { type: 'warning' })
  const completed = transfers.tasks.filter((t) => t.status === 'completed')
  await Promise.allSettled(completed.map((t) => transfers.cancelTask(t.id)))
  ElMessage.success('已清除')
}

onMounted(() => {
  transfers.fetchTasks()
  wsConnect()
})
</script>

<style scoped>
.transfer-tasks { display: flex; flex-direction: column; gap: 16px; height: 100%; }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.page-header h2 { font-size: 20px; }
.header-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.task-list { flex: 1; display: flex; flex-direction: column; gap: 12px; overflow: auto; }
.transfer-footer {
  display: flex; gap: 24px; align-items: center; padding: 12px 16px;
  background: var(--card-bg); border-radius: 8px; font-size: 13px; color: var(--text-regular);
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.stat { display: flex; align-items: center; gap: 6px; }
.ws-status { margin-left: auto; }
.ws-dot { width: 8px; height: 8px; border-radius: 50%; }
.ws-dot.connected { background: var(--success-color); }
.ws-dot.disconnected { background: var(--danger-color); }
</style>
