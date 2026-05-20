<template>
  <div class="share-manager">
    <div class="page-header">
      <h2>分享链接</h2>
      <div class="header-actions responsive-filters">
        <el-select v-model="statusFilter" placeholder="状态" clearable>
          <el-option label="启用中" value="active" />
          <el-option label="已停用" value="inactive" />
          <el-option label="已过期" value="expired" />
        </el-select>
        <el-button :icon="Refresh" @click="fetchShares" :loading="loading">刷新</el-button>
      </div>
    </div>

    <el-table :data="filteredShares" v-loading="loading" style="width: 100%">
      <el-table-column label="文件" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <div class="file-cell">
            <el-icon><Document /></el-icon>
            <div>
              <div class="file-name">{{ fileName(row.file_path) }}</div>
              <div class="file-path">{{ row.file_path }}</div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="shareStatus(row).type" size="small">{{ shareStatus(row).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="访问" width="110" align="center">
        <template #default="{ row }">
          {{ row.view_count }}<span v-if="row.max_views"> / {{ row.max_views }}</span>
        </template>
      </el-table-column>
      <el-table-column label="过期时间" width="180" class-name="hide-sm" label-class-name="hide-sm">
        <template #default="{ row }">{{ row.expires_at ? formatTime(row.expires_at) : '永不过期' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="180" class-name="hide-sm" label-class-name="hide-sm">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="142" fixed="right" align="center" class-name="operation-column">
        <template #default="{ row }">
          <div class="row-actions">
            <el-tooltip content="复制链接" placement="top" :show-after="250">
              <el-button class="action-button" text :icon="CopyDocument" aria-label="复制链接" @click="copyLink(row)" />
            </el-tooltip>
            <el-dropdown trigger="click" placement="bottom-end" @command="(command) => handleCommand(command, row)">
              <el-button class="action-button" text :icon="MoreFilled" aria-label="更多操作" />
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-if="row.is_active" command="deactivate">停用</el-dropdown-item>
                  <el-dropdown-item class="danger-action" command="delete" :icon="Delete" divided>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && filteredShares.length === 0" description="暂无分享链接" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CopyDocument, Delete, Document, MoreFilled, Refresh } from '@element-plus/icons-vue'
import { deactivateShare, deleteShare, listAllShares, listMyShares } from '@/api/shares'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const shares = ref([])
const statusFilter = ref('')

const filteredShares = computed(() => {
  if (!statusFilter.value) return shares.value
  return shares.value.filter((share) => {
    const status = shareStatus(share).value
    return status === statusFilter.value
  })
})

function fileName(path) {
  return path?.split('/').filter(Boolean).pop() || path || '-'
}

function formatTime(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

function isExpired(share) {
  return share.expires_at && new Date(share.expires_at).getTime() < Date.now()
}

function shareStatus(share) {
  if (!share.is_active) return { value: 'inactive', label: '已停用', type: 'info' }
  if (isExpired(share)) return { value: 'expired', label: '已过期', type: 'warning' }
  return { value: 'active', label: '启用中', type: 'success' }
}

function shareUrl(share) {
  return `${location.origin}/share/${share.token}`
}

async function fetchShares() {
  loading.value = true
  try {
    shares.value = auth.isAdmin ? await listAllShares() : await listMyShares()
  } finally {
    loading.value = false
  }
}

async function copyLink(share) {
  await navigator.clipboard.writeText(shareUrl(share))
  ElMessage.success('分享链接已复制')
}

async function handleCommand(command, share) {
  if (command === 'deactivate') {
    await deactivateShare(share.id)
    ElMessage.success('分享链接已停用')
    fetchShares()
  } else if (command === 'delete') {
    await ElMessageBox.confirm(`确定删除 "${fileName(share.file_path)}" 的分享链接?`, '删除分享链接', { type: 'warning' })
    await deleteShare(share.id)
    ElMessage.success('分享链接已删除')
    fetchShares()
  }
}

onMounted(fetchShares)
</script>

<style scoped>
.share-manager { display: flex; flex-direction: column; gap: 16px; }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.page-header h2 { font-size: 20px; }
.header-actions.responsive-filters { display: grid; }
.file-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.file-name {
  font-weight: 600;
  color: var(--text-primary);
}
.file-path {
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
  font-size: 12px;
}
.row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
}
.action-button {
  width: 30px;
  height: 30px;
  padding: 0;
  border-radius: 6px;
  color: var(--el-color-primary);
}
.action-button:hover,
.action-button:focus-visible {
  background: var(--el-color-primary-light-9);
}
:deep(.operation-column .cell) {
  padding-left: 6px;
  padding-right: 6px;
}
@media (max-width: 768px) {
  .page-header {
    align-items: stretch;
    flex-direction: column;
  }
  .file-path {
    max-width: 220px;
  }
}
</style>
