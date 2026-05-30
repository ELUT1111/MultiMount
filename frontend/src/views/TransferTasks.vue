<template>
  <div class="transfer-tasks">
    <PageHeader
      title="传输任务"
      :meta="[
        `${runningCount} 个进行中`,
        `${completedCount} 个已完成`,
        `${failedCount} 个失败`,
      ]"
      actions-layout="flex"
    >
      <template #actions>
        <el-button @click="transfers.fetchTasks()" :icon="Refresh">刷新</el-button>
        <el-button @click="handleBatchPause" :disabled="!transfers.activeCount">全部暂停</el-button>
        <el-button type="primary" @click="handleBatchResume">全部继续</el-button>
        <el-button type="danger" plain @click="handleBatchCancel" :disabled="!runningCount">全部取消</el-button>
        <el-button @click="handleClearCompleted" :disabled="!completedCount">清除已完成</el-button>
      </template>
    </PageHeader>

    <section class="transfer-overview" aria-label="传输概览">
      <div class="overview-card speed-card">
        <span class="overview-label">实时速度</span>
        <strong>{{ formatSpeed(transfers.totalTransferSpeed) }}</strong>
        <small>{{ wsConnected ? 'WebSocket 实时同步' : '等待同步连接' }}</small>
      </div>
      <div class="overview-card active-card">
        <span class="overview-label">活跃任务</span>
        <strong>{{ transfers.activeCount }}</strong>
        <small>{{ queuedCount }} 个排队，{{ pausedCount }} 个暂停</small>
      </div>
      <div class="overview-card complete-card">
        <span class="overview-label">完成率</span>
        <strong>{{ completionRate }}%</strong>
        <small>{{ completedCount }} / {{ transfers.tasks.length || 0 }} 个任务</small>
      </div>
      <div class="overview-card sync-card" :class="wsConnected ? 'is-online' : 'is-offline'">
        <span class="overview-label">同步状态</span>
        <strong>
          <span class="ws-dot" :class="wsConnected ? 'connected' : 'disconnected'" />
          {{ wsConnected ? '在线' : '离线' }}
        </strong>
        <small>{{ failedCount ? `${failedCount} 个任务需要处理` : '当前无异常任务' }}</small>
      </div>
    </section>

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
      <el-empty v-if="!transfers.loading && transfers.filteredTasks.length === 0" :description="emptyDescription" />

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
import PageHeader from '@/components/common/PageHeader.vue'
import TransferCard from '@/components/transfer/TransferCard.vue'

const transfers = useTransfersStore()

const { data: wsData, connected: wsConnected, connect: wsConnect } = useWebSocket(
  buildWebSocketUrl('/api/v1/transfers/ws'),
)

const activeStatuses = ['queued', 'pending', 'running', 'paused']
const runningCount = computed(() => transfers.tasks.filter((t) => activeStatuses.includes(t.status)).length)
const completedCount = computed(() => transfers.tasks.filter((t) => t.status === 'completed').length)
const failedCount = computed(() => transfers.tasks.filter((t) => t.status === 'failed').length)
const queuedCount = computed(() => transfers.tasks.filter((t) => ['queued', 'pending'].includes(t.status)).length)
const pausedCount = computed(() => transfers.tasks.filter((t) => t.status === 'paused').length)
const completionRate = computed(() => {
  if (!transfers.tasks.length) return 0
  return Math.round((completedCount.value / transfers.tasks.length) * 100)
})
const emptyDescription = computed(() => ({
  running: '暂无进行中的复制/移动任务',
  completed: '暂无已完成任务',
  failed: '暂无失败任务',
}[transfers.activeTab] || '暂无复制/移动任务'))

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
.transfer-overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.overview-card {
  position: relative;
  min-height: 92px;
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--card-bg);
  overflow: hidden;
}
.overview-card::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--primary-color);
}
.speed-card::before { background: var(--primary-color); }
.active-card::before { background: var(--warning-color); }
.complete-card::before { background: var(--success-color); }
.sync-card::before { background: var(--danger-color); }
.sync-card.is-online::before { background: var(--success-color); }
.overview-label {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
}
.overview-card strong {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  color: var(--text-regular);
  font-size: 24px;
  line-height: 1.15;
}
.overview-card small {
  display: block;
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
}
.task-list { flex: 1; display: flex; flex-direction: column; gap: 12px; overflow: auto; padding-right: 2px; }
.transfer-footer {
  display: flex; gap: 24px; align-items: center; padding: 12px 16px;
  background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 10px; font-size: 13px; color: var(--text-regular);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}
.stat { display: flex; align-items: center; gap: 6px; }
.ws-status { margin-left: auto; }
.ws-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-flex;
  flex: 0 0 8px;
  box-shadow: 0 0 0 4px color-mix(in srgb, currentColor 16%, transparent);
}
.ws-dot.connected { background: var(--success-color); color: var(--success-color); }
.ws-dot.disconnected { background: var(--danger-color); color: var(--danger-color); }

@media (max-width: 1100px) {
  .transfer-overview { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .transfer-overview { grid-template-columns: 1fr; }
  .transfer-footer { flex-wrap: wrap; gap: 10px 16px; }
  .ws-status { margin-left: 0; }
}
</style>
