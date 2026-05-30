<template>
  <div class="trash-manager">
    <PageHeader
      title="回收站"
      :meta="[
        `${filteredItems.length} / ${items.length} 个项目`,
        formatSize(totalTrashSize),
        `${stats.length} 个挂载源`,
      ]"
    >
      <template #actions>
        <el-select v-model="mountFilter" placeholder="挂载源" clearable>
          <el-option
            v-for="mount in mounts.mounts"
            :key="mount.id"
            :label="mount.name"
            :value="mount.id"
          />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索文件名或路径" clearable />
        <el-select v-model="restorePolicy" placeholder="恢复策略">
          <el-option label="自动重命名" value="rename" />
          <el-option label="覆盖" value="overwrite" />
          <el-option label="跳过" value="skip" />
          <el-option label="报错" value="error" />
        </el-select>
        <el-button :icon="Refresh" @click="fetchTrash" :loading="loading">刷新</el-button>
      </template>
    </PageHeader>

    <div class="stats-row">
      <div v-for="stat in stats" :key="stat.mount_id" class="stat-card">
        <div class="stat-title">{{ mountName(stat.mount_id) }}</div>
        <div class="stat-main">{{ formatSize(stat.total_size) }}</div>
        <div class="stat-sub">{{ stat.item_count }} 项 · 最早 {{ formatTime(stat.oldest_deleted_at) }}</div>
      </div>
      <el-empty v-if="!stats.length && !loading" description="暂无回收站统计" :image-size="48" />
    </div>

    <BatchToolbar v-if="selectedItems.length" :summary="`已选择 ${selectedItems.length} 个项目`">
      <el-button size="small" type="primary" plain :icon="RefreshLeft" @click="handleBatchRestore">
        恢复
      </el-button>
      <el-button size="small" type="danger" plain :icon="Delete" @click="handleBatchPurge">
        彻底删除
      </el-button>
      <el-button size="small" @click="clearSelection">清空选择</el-button>
    </BatchToolbar>

    <div class="maintenance-panel">
      <div class="maintenance-fields">
        <label class="maintenance-field">
          <span>保留天数</span>
          <el-input-number v-model="cleanup.retention_days" :min="0" :step="1" controls-position="right" />
        </label>
        <label class="maintenance-field">
          <span>容量上限 MB</span>
          <el-input-number v-model="cleanup.max_total_size_mb" :min="0" :step="100" controls-position="right" />
        </label>
        <el-button :icon="Refresh" @click="handleCleanup">执行清理</el-button>
      </div>
      <div class="danger-actions">
        <el-button type="danger" plain @click="handleClearFiltered" :disabled="!filteredItems.length">清空筛选结果</el-button>
        <el-button type="danger" plain @click="handleClearMount" :disabled="!mountFilter">清空当前挂载</el-button>
        <el-button type="danger" @click="handleClearAll" :disabled="!items.length">清空全部</el-button>
      </div>
    </div>

    <div class="table-shell">
      <el-table
        ref="trashTableRef"
        :data="filteredItems"
        v-loading="loading"
        row-key="id"
        style="width: 100%"
        @selection-change="selectedItems = $event"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column label="文件" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="file-cell">
              <div class="file-icon">
                <el-icon><Folder v-if="row.is_dir" /><Document v-else /></el-icon>
              </div>
              <div class="file-copy">
                <div class="file-name">{{ row.name }}</div>
                <div class="file-path">{{ row.original_path }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="挂载源" width="140" class-name="hide-sm" label-class-name="hide-sm">
          <template #default="{ row }">{{ mountName(row.mount_id) }}</template>
        </el-table-column>
        <el-table-column label="大小" width="110" class-name="hide-sm" label-class-name="hide-sm">
          <template #default="{ row }">{{ row.is_dir ? '-' : formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column label="删除者" width="120" class-name="hide-sm" label-class-name="hide-sm">
          <template #default="{ row }">{{ row.deleted_by_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="删除时间" width="180">
          <template #default="{ row }">{{ formatTime(row.deleted_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="132" fixed="right" align="center" class-name="operation-column">
          <template #default="{ row }">
            <div class="row-actions">
              <el-tooltip content="恢复" placement="top" :show-after="250">
                <el-button class="action-button" text :icon="RefreshLeft" aria-label="恢复" @click="handleRestore(row)" />
              </el-tooltip>
              <el-tooltip content="彻底删除" placement="top" :show-after="250">
                <el-button class="action-button danger-button" text :icon="Delete" aria-label="彻底删除" @click="handlePurge(row)" />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-empty v-if="!loading && filteredItems.length === 0" description="回收站为空" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Document, Folder, Refresh, RefreshLeft } from '@element-plus/icons-vue'
import { clearTrash, getTrashStats, listTrashItems, purgeTrashItem, restoreTrashItem } from '@/api/trash'
import { formatSize, formatTime } from '@/utils/format'
import { useMountsStore } from '@/stores/mounts'
import BatchToolbar from '@/components/common/BatchToolbar.vue'
import PageHeader from '@/components/common/PageHeader.vue'

const mounts = useMountsStore()
const loading = ref(false)
const items = ref([])
const selectedItems = ref([])
const trashTableRef = ref()
const keyword = ref('')
const mountFilter = ref('')
const restorePolicy = ref('rename')
const stats = ref([])
const cleanup = ref({ retention_days: 0, max_total_size_mb: 0 })

const filteredItems = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return items.value.filter((item) => {
    const matchesMount = !mountFilter.value || item.mount_id === mountFilter.value
    const matchesKeyword = !q || item.name.toLowerCase().includes(q) || item.original_path.toLowerCase().includes(q)
    return matchesMount && matchesKeyword
  })
})

const totalTrashSize = computed(() =>
  stats.value.reduce((total, stat) => total + (Number(stat.total_size) || 0), 0)
)

function mountName(mountId) {
  return mounts.mounts.find((mount) => mount.id === mountId)?.name || `#${mountId}`
}

async function fetchTrash() {
  loading.value = true
  try {
    items.value = await listTrashItems()
    stats.value = await getTrashStats()
    clearSelection()
  } finally {
    loading.value = false
  }
}

function clearSelection() {
  selectedItems.value = []
  trashTableRef.value?.clearSelection?.()
}

async function handleRestore(item) {
  await restoreTrashItem(item.id, restorePolicy.value)
  ElMessage.success('已恢复')
  fetchTrash()
}

async function handlePurge(item) {
  await ElMessageBox.confirm(`确定彻底删除 "${item.name}"? 此操作不可恢复。`, '彻底删除', { type: 'warning' })
  await purgeTrashItem(item.id)
  ElMessage.success('已彻底删除')
  fetchTrash()
}

async function runBatch(action) {
  const targets = [...selectedItems.value]
  if (!targets.length) return
  if (action === 'purge') {
    await ElMessageBox.confirm(`确定彻底删除选中的 ${targets.length} 个项目? 此操作不可恢复。`, '彻底删除', { type: 'warning' })
  }

  const results = await Promise.allSettled(
    targets.map((item) => action === 'restore' ? restoreTrashItem(item.id, restorePolicy.value) : purgeTrashItem(item.id))
  )
  const failed = results.filter((result) => result.status === 'rejected').length
  const success = targets.length - failed
  if (failed) ElMessage.warning(`操作完成: ${success} 个成功, ${failed} 个失败`)
  else ElMessage.success(`操作完成: ${success} 个项目`)
  fetchTrash()
}

function handleBatchRestore() {
  runBatch('restore')
}

function handleBatchPurge() {
  runBatch('purge')
}

async function runClear(payload, title) {
  await ElMessageBox.confirm(`${title}? 此操作不可恢复。`, title, { type: 'warning' })
  const result = await clearTrash(payload)
  if (result.failed_count) ElMessage.warning(`完成: ${result.success_count} 成功, ${result.failed_count} 失败`)
  else ElMessage.success(`已清理 ${result.success_count} 个项目`)
  fetchTrash()
}

function handleClearFiltered() {
  runClear({ scope: 'filtered', item_ids: filteredItems.value.map((item) => item.id), mount_id: mountFilter.value || null }, '清空筛选结果')
}

function handleClearMount() {
  runClear({ scope: 'mount', mount_id: mountFilter.value }, '清空当前挂载回收站')
}

function handleClearAll() {
  runClear({ scope: 'all' }, '清空全部回收站')
}

function handleCleanup() {
  const max_total_size = Math.round((cleanup.value.max_total_size_mb || 0) * 1024 * 1024)
  runClear({
    scope: mountFilter.value ? 'mount' : 'all',
    mount_id: mountFilter.value || null,
    retention_days: cleanup.value.retention_days || 0,
    max_total_size,
  }, '执行回收站自动清理')
}

onMounted(async () => {
  await mounts.fetchMounts()
  fetchTrash()
})
</script>

<style scoped>
.trash-manager {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(220px, 100%), 1fr));
  gap: 12px;
}
.stat-card {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--card-bg);
}
.stat-title { font-size: 13px; color: var(--text-secondary); }
.stat-main { margin-top: 4px; font-size: 18px; font-weight: 700; color: var(--text-primary); }
.stat-sub {
  overflow: hidden;
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.maintenance-panel {
  display: grid;
  grid-template-columns: minmax(300px, 1fr) auto;
  gap: 12px;
  align-items: end;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--card-bg);
}
.maintenance-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(150px, 180px)) auto;
  gap: 10px;
  align-items: end;
}
.maintenance-field {
  display: grid;
  gap: 5px;
  color: var(--text-secondary);
  font-size: 13px;
}
.maintenance-field :deep(.el-input-number),
.maintenance-fields :deep(.el-button) {
  width: 100%;
}
.danger-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}
.table-shell {
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--card-bg);
}
.file-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.file-icon {
  display: grid;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  place-items: center;
  border: 1px solid rgba(64, 158, 255, 0.2);
  border-radius: 8px;
  background: rgba(64, 158, 255, 0.08);
  color: var(--primary-color);
}
.file-copy {
  min-width: 0;
}
.file-name {
  overflow: hidden;
  font-weight: 600;
  color: var(--text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-path {
  max-width: 460px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
  font-size: 12px;
}
.row-actions { display: inline-flex; align-items: center; justify-content: center; gap: 4px; width: 100%; }
.action-button {
  width: 30px;
  height: 30px;
  padding: 0;
  border-radius: 6px;
  color: var(--el-color-primary);
}
.action-button:hover,
.action-button:focus-visible { background: var(--el-color-primary-light-9); }
.danger-button { color: var(--el-color-danger); }
.danger-button:hover,
.danger-button:focus-visible {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}
:deep(.operation-column .cell) { padding-left: 6px; padding-right: 6px; }

@media (max-width: 1180px) {
  .maintenance-panel {
    grid-template-columns: 1fr;
    align-items: start;
  }
  .danger-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .trash-manager {
    gap: 14px;
  }
  .maintenance-fields {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .maintenance-fields > :deep(.el-button) {
    grid-column: 1 / -1;
  }
  .danger-actions :deep(.el-button) {
    flex: 1 1 150px;
  }
  .file-path { max-width: 220px; }
}

@media (max-width: 480px) {
  .maintenance-fields {
    grid-template-columns: 1fr;
  }
}
</style>
