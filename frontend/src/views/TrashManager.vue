<template>
  <div class="trash-manager">
    <div class="page-header">
      <div>
        <h2>回收站</h2>
        <p>已删除的文件会保留在对应挂载源中，可恢复或彻底删除。</p>
      </div>
      <div class="header-actions responsive-filters">
        <el-select v-model="mountFilter" placeholder="挂载源" clearable>
          <el-option
            v-for="mount in mounts.mounts"
            :key="mount.id"
            :label="mount.name"
            :value="mount.id"
          />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索文件名或路径" clearable />
        <el-button :icon="Refresh" @click="fetchTrash" :loading="loading">刷新</el-button>
      </div>
    </div>

    <div v-if="selectedItems.length" class="batch-toolbar">
      <span>已选择 {{ selectedItems.length }} 个项目</span>
      <div class="batch-actions">
        <el-button size="small" type="primary" plain :icon="RefreshLeft" @click="handleBatchRestore">
          恢复
        </el-button>
        <el-button size="small" type="danger" plain :icon="Delete" @click="handleBatchPurge">
          彻底删除
        </el-button>
        <el-button size="small" @click="clearSelection">清空选择</el-button>
      </div>
    </div>

    <el-table
      ref="trashTableRef"
      :data="filteredItems"
      v-loading="loading"
      row-key="id"
      style="width: 100%"
      @selection-change="selectedItems = $event"
    >
      <el-table-column type="selection" width="44" />
      <el-table-column label="文件" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">
          <div class="file-cell">
            <el-icon><Folder v-if="row.is_dir" /><Document v-else /></el-icon>
            <div>
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
      <el-table-column label="操作" width="142" fixed="right" align="center" class-name="operation-column">
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

    <el-empty v-if="!loading && filteredItems.length === 0" description="回收站为空" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Document, Folder, Refresh, RefreshLeft } from '@element-plus/icons-vue'
import { listTrashItems, purgeTrashItem, restoreTrashItem } from '@/api/trash'
import { formatSize, formatTime } from '@/utils/format'
import { useMountsStore } from '@/stores/mounts'

const mounts = useMountsStore()
const loading = ref(false)
const items = ref([])
const selectedItems = ref([])
const trashTableRef = ref()
const keyword = ref('')
const mountFilter = ref('')

const filteredItems = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return items.value.filter((item) => {
    const matchesMount = !mountFilter.value || item.mount_id === mountFilter.value
    const matchesKeyword = !q || item.name.toLowerCase().includes(q) || item.original_path.toLowerCase().includes(q)
    return matchesMount && matchesKeyword
  })
})

function mountName(mountId) {
  return mounts.mounts.find((mount) => mount.id === mountId)?.name || `#${mountId}`
}

async function fetchTrash() {
  loading.value = true
  try {
    items.value = await listTrashItems()
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
  await restoreTrashItem(item.id, 'rename')
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
    targets.map((item) => action === 'restore' ? restoreTrashItem(item.id, 'rename') : purgeTrashItem(item.id))
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

onMounted(async () => {
  await mounts.fetchMounts()
  fetchTrash()
})
</script>

<style scoped>
.trash-manager { display: flex; flex-direction: column; gap: 16px; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; }
.page-header p { margin: 0; color: var(--text-secondary); font-size: 13px; }
.header-actions.responsive-filters { display: grid; }
.batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(64,158,255,0.08);
  border: 1px solid rgba(64,158,255,0.18);
  border-radius: 8px;
  font-size: 13px;
}
.batch-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.file-cell { display: flex; align-items: center; gap: 10px; min-width: 0; }
.file-name { font-weight: 600; color: var(--text-primary); }
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

@media (max-width: 768px) {
  .page-header { flex-direction: column; align-items: stretch; }
  .batch-toolbar { align-items: flex-start; flex-direction: column; }
  .batch-actions { width: 100%; }
  .batch-actions :deep(.el-button) { flex: 1 1 120px; }
  .file-path { max-width: 220px; }
}
</style>
