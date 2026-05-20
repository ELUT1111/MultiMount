<template>
  <div class="share-manager">
    <div class="page-header">
      <div class="header-copy">
        <h2>分享链接</h2>
        <div class="header-meta">
          <span>{{ filteredShares.length }} / {{ shares.length }} 条分享</span>
          <span>{{ activeShareCount }} 条启用</span>
          <span>{{ expiredShareCount }} 条过期</span>
        </div>
      </div>
      <div class="header-actions responsive-filters">
        <el-select v-model="statusFilter" placeholder="状态" clearable>
          <el-option label="启用中" value="active" />
          <el-option label="已停用" value="inactive" />
          <el-option label="已过期" value="expired" />
        </el-select>
        <el-input v-model="creatorFilter" placeholder="创建者 ID" clearable />
        <el-input v-model.number="mountFilter" placeholder="挂载 ID" clearable />
        <el-button v-if="auth.isAdmin" @click="openPolicy">安全策略</el-button>
        <el-button :icon="Refresh" @click="fetchShares" :loading="loading">刷新</el-button>
      </div>
    </div>

    <div v-if="selectedShares.length" class="batch-toolbar">
      <span>已选择 {{ selectedShares.length }} 条分享</span>
      <div class="batch-actions">
        <el-button size="small" @click="handleBatch('deactivate')">批量停用</el-button>
        <el-button size="small" type="danger" plain @click="handleBatch('delete')">批量删除</el-button>
      </div>
    </div>

    <div class="table-shell">
      <el-table
        :data="filteredShares"
        v-loading="loading"
        row-key="id"
        style="width: 100%"
        @selection-change="selectedShares = $event"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column label="文件" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="file-cell">
              <div class="file-icon">
                <el-icon><Folder v-if="row.is_dir" /><Document v-else /></el-icon>
              </div>
              <div class="file-copy">
                <div class="file-name">{{ fileName(row.file_path) }}</div>
                <div class="file-path">{{ row.file_path }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="104" align="center">
          <template #default="{ row }">
            <el-tag :type="shareStatus(row).type" size="small" effect="plain">{{ shareStatus(row).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="访问" width="110" align="center">
          <template #default="{ row }">
            {{ row.view_count }}<span v-if="row.max_views"> / {{ row.max_views }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建者" width="96" class-name="hide-sm" label-class-name="hide-sm">
          <template #default="{ row }">#{{ row.created_by }}</template>
        </el-table-column>
        <el-table-column label="挂载" width="88" class-name="hide-sm" label-class-name="hide-sm">
          <template #default="{ row }">#{{ row.mount_id }}</template>
        </el-table-column>
        <el-table-column label="过期时间" width="180" class-name="hide-sm" label-class-name="hide-sm">
          <template #default="{ row }">{{ row.expires_at ? formatTime(row.expires_at) : '永不过期' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="136" fixed="right" align="center" class-name="operation-column">
          <template #default="{ row }">
            <div class="row-actions">
              <el-tooltip content="复制链接" placement="top" :show-after="250">
                <el-button class="action-button" text :icon="CopyDocument" aria-label="复制链接" @click="copyLink(row)" />
              </el-tooltip>
              <el-dropdown trigger="click" placement="bottom-end" @command="(command) => handleCommand(command, row)">
                <el-button class="action-button" text :icon="MoreFilled" aria-label="更多操作" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit" :icon="Edit">编辑</el-dropdown-item>
                    <el-dropdown-item command="stats">访问统计</el-dropdown-item>
                    <el-dropdown-item v-if="row.is_active" command="deactivate">停用</el-dropdown-item>
                    <el-dropdown-item class="danger-action" command="delete" :icon="Delete" divided>删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-empty v-if="!loading && filteredShares.length === 0" description="暂无分享链接" />

    <el-dialog v-model="showEditDialog" title="编辑分享链接" class="responsive-dialog share-dialog" append-to-body>
      <el-form label-width="110px">
        <el-form-item label="有效期">
          <el-input-number v-model="editForm.expires_hours" :min="0" :max="8760" controls-position="right" />
          <span class="field-hint">小时，0 表示永不过期</span>
        </el-form-item>
        <el-form-item label="访问次数">
          <el-input-number v-model="editForm.max_views" :min="0" controls-position="right" />
        </el-form-item>
        <el-form-item label="提取码">
          <el-input v-model="editForm.access_code" placeholder="留空表示清除提取码" show-password />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="editForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showStatsDialog" title="分享访问统计" class="responsive-dialog share-stats-dialog" append-to-body>
      <div class="stats-summary">
        <span>访问 {{ statsData.view_count || 0 }} 次</span>
        <span>下载 {{ statsData.download_count || 0 }} 次</span>
      </div>
      <el-table :data="statsData.events || []" size="small" max-height="360">
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="action" label="动作" width="130" />
        <el-table-column prop="ip_address" label="IP" width="140" />
        <el-table-column prop="user_agent" label="来源" min-width="220" show-overflow-tooltip />
      </el-table>
    </el-dialog>

    <el-dialog v-model="showPolicyDialog" title="分享安全策略" class="responsive-dialog share-policy-dialog" append-to-body>
      <el-form label-width="130px">
        <el-form-item label="允许分享">
          <el-switch v-model="policy.enabled" />
        </el-form-item>
        <el-form-item label="强制提取码">
          <el-switch v-model="policy.force_access_code" />
        </el-form-item>
        <el-form-item label="默认有效期">
          <el-input-number v-model="policy.default_expires_hours" :min="0" :max="8760" controls-position="right" />
          <span class="field-hint">小时</span>
        </el-form-item>
        <el-form-item label="每小时访问上限">
          <el-input-number v-model="policy.max_access_per_hour" :min="0" controls-position="right" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPolicyDialog = false">取消</el-button>
        <el-button type="primary" @click="savePolicy">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CopyDocument, Delete, Document, Edit, Folder, MoreFilled, Refresh } from '@element-plus/icons-vue'
import {
  batchShare,
  deactivateShare,
  deleteShare,
  getSharePolicy,
  getShareStats,
  listAllShares,
  listMyShares,
  updateShare,
  updateSharePolicy,
} from '@/api/shares'
import { formatTime } from '@/utils/format'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const shares = ref([])
const selectedShares = ref([])
const statusFilter = ref('')
const creatorFilter = ref('')
const mountFilter = ref('')
const showEditDialog = ref(false)
const editingShare = ref(null)
const editForm = ref({ expires_hours: 0, max_views: 0, access_code: '', is_active: true })
const showStatsDialog = ref(false)
const statsData = ref({})
const showPolicyDialog = ref(false)
const policy = ref({ enabled: true, force_access_code: false, default_expires_hours: 0, max_access_per_hour: 0 })

const filteredShares = computed(() => shares.value.filter((share) => {
  if (statusFilter.value && shareStatus(share).value !== statusFilter.value) return false
  if (creatorFilter.value && String(share.created_by) !== String(creatorFilter.value)) return false
  if (mountFilter.value && Number(share.mount_id) !== Number(mountFilter.value)) return false
  return true
}))

const activeShareCount = computed(() => shares.value.filter((share) => shareStatus(share).value === 'active').length)
const expiredShareCount = computed(() => shares.value.filter((share) => shareStatus(share).value === 'expired').length)

function fileName(path) {
  return path?.split('/').filter(Boolean).pop() || path || '-'
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

function openEdit(share) {
  editingShare.value = share
  editForm.value = {
    expires_hours: 0,
    max_views: share.max_views || 0,
    access_code: '',
    is_active: share.is_active,
  }
  showEditDialog.value = true
}

async function saveEdit() {
  await updateShare(editingShare.value.id, editForm.value)
  ElMessage.success('分享链接已更新')
  showEditDialog.value = false
  fetchShares()
}

async function openStats(share) {
  statsData.value = await getShareStats(share.id)
  showStatsDialog.value = true
}

async function handleBatch(action) {
  await ElMessageBox.confirm(`确定${action === 'delete' ? '删除' : '停用'}选中的 ${selectedShares.value.length} 条分享?`, '批量管理', { type: 'warning' })
  const result = await batchShare({ action, ids: selectedShares.value.map((share) => share.id) })
  if (result.failed_count) ElMessage.warning(`完成: ${result.success_count} 成功, ${result.failed_count} 失败`)
  else ElMessage.success('批量操作完成')
  fetchShares()
}

async function openPolicy() {
  policy.value = await getSharePolicy()
  showPolicyDialog.value = true
}

async function savePolicy() {
  await updateSharePolicy(policy.value)
  ElMessage.success('分享安全策略已保存')
  showPolicyDialog.value = false
}

async function handleCommand(command, share) {
  if (command === 'edit') openEdit(share)
  else if (command === 'stats') openStats(share)
  else if (command === 'deactivate') {
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
.share-manager {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.page-header {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(560px, 820px);
  gap: 16px;
  align-items: end;
}
.header-copy {
  min-width: 0;
}
.page-header h2 {
  margin-bottom: 8px;
  font-size: 22px;
  line-height: 1.25;
}
.header-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}
.header-meta span {
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--card-bg);
  padding: 3px 10px;
}
.header-actions.responsive-filters {
  display: grid;
  grid-template-columns: repeat(5, minmax(112px, 1fr));
  gap: 10px;
  align-items: center;
}
.header-actions :deep(.el-input),
.header-actions :deep(.el-select),
.header-actions :deep(.el-button) {
  width: 100%;
  min-width: 0;
}
.batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(64, 158, 255, 0.08);
  border: 1px solid rgba(64, 158, 255, 0.18);
  color: var(--text-regular);
  font-size: 13px;
}
.batch-actions {
  display: flex;
  align-items: center;
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
  color: var(--text-primary);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
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
.action-button:focus-visible { background: var(--el-color-primary-light-9); }
.field-hint {
  margin-left: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}
.stats-summary {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  color: var(--text-secondary);
}
:deep(.operation-column .cell) { padding-left: 6px; padding-right: 6px; }
 :deep(.share-dialog .el-input-number),
 :deep(.share-policy-dialog .el-input-number) {
  width: 180px;
}
@media (max-width: 1180px) {
  .page-header {
    grid-template-columns: 1fr;
    align-items: start;
  }
  .header-actions.responsive-filters {
    grid-template-columns: repeat(5, minmax(112px, 1fr));
  }
}
@media (max-width: 768px) {
  .share-manager {
    gap: 14px;
  }
  .page-header {
    gap: 12px;
  }
  .page-header h2 {
    font-size: 20px;
  }
  .header-actions.responsive-filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .batch-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .batch-actions {
    width: 100%;
  }
  .batch-actions :deep(.el-button) {
    flex: 1 1 120px;
  }
  .file-path { max-width: 220px; }
  :deep(.share-dialog .el-form-item),
  :deep(.share-policy-dialog .el-form-item) {
    display: block;
  }
  :deep(.share-dialog .el-form-item__label),
  :deep(.share-policy-dialog .el-form-item__label) {
    justify-content: flex-start;
    margin-bottom: 4px;
  }
  :deep(.share-dialog .el-input-number),
  :deep(.share-policy-dialog .el-input-number) {
    width: 100%;
  }
  .field-hint {
    display: block;
    margin: 6px 0 0;
  }
}
@media (max-width: 480px) {
  .header-actions.responsive-filters {
    grid-template-columns: 1fr;
  }
}
</style>
