<!--
  用户表格组件 — 展示用户列表, 支持搜索/角色/状态筛选和编辑/禁用/删除操作。
-->
<template>
  <div class="user-table">
    <div class="table-toolbar">
      <div class="toolbar-filters responsive-filters">
        <el-input v-model="search" placeholder="搜索用户名/邮箱..." :prefix-icon="Search" clearable />
        <el-select v-model="filterRole" placeholder="角色" clearable>
          <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.name" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="状态" clearable>
          <el-option label="启用" :value="true" />
          <el-option label="禁用" :value="false" />
        </el-select>
      </div>
      <el-button type="primary" :icon="Plus" @click="$emit('add')">添加用户</el-button>
    </div>
    <div class="table-shell">
      <el-table :data="filtered" style="width:100%" v-loading="loading">
        <el-table-column label="用户" min-width="220">
          <template #default="{ row }">
            <div class="user-cell">
              <div class="user-avatar">{{ userInitial(row.username) }}</div>
              <div class="user-copy">
                <div class="user-name">{{ row.username }}</div>
                <div class="user-email">{{ row.email || '-' }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="130">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.role?.name || '未分配' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <StatusBadge :status="row.is_active ? 'online' : 'offline'" :label="row.is_active ? '启用' : '禁用'" />
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="170" class-name="hide-sm" label-class-name="hide-sm">
          <template #default="{ row }">{{ formatTime(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="118" fixed="right" align="center" class-name="operation-column">
          <template #default="{ row }">
            <div class="row-actions">
              <el-tooltip content="编辑" placement="top" :show-after="250">
                <el-button class="action-button" text :icon="Edit" aria-label="编辑" @click="$emit('edit', row)" />
              </el-tooltip>
              <el-dropdown trigger="click" placement="bottom-end" @command="(command) => handleCommand(command, row)">
                <el-button class="action-button" text :icon="MoreFilled" aria-label="更多操作" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="toggle" :icon="SwitchButton">
                      {{ row.is_active ? '禁用' : '启用' }}
                    </el-dropdown-item>
                    <el-dropdown-item class="danger-action" command="delete" :icon="Delete" divided>删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Delete, Edit, MoreFilled, Plus, Search, SwitchButton } from '@element-plus/icons-vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { formatTime } from '@/utils/format'

const props = defineProps({
  users: { type: Array, default: () => [] },
  roles: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['add', 'edit', 'toggle', 'delete'])

const search = ref('')
const filterRole = ref('')
const filterStatus = ref('')

const filtered = computed(() =>
  props.users.filter((u) => {
    if (search.value && !u.username.includes(search.value) && !u.email?.includes(search.value)) return false
    if (filterRole.value && u.role?.name !== filterRole.value) return false
    if (filterStatus.value !== '' && u.is_active !== filterStatus.value) return false
    return true
  })
)

function handleCommand(command, row) {
  if (command === 'toggle') emit('toggle', row)
  else if (command === 'delete') emit('delete', row)
}

function userInitial(username) {
  return String(username || 'U').slice(0, 1).toUpperCase()
}
</script>

<style scoped>
.user-table {
  min-width: 0;
}
.table-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  margin-bottom: 14px;
}
.toolbar-filters {
  gap: 10px;
  align-items: center;
}
.toolbar-filters.responsive-filters {
  display: grid;
  grid-template-columns: minmax(180px, 1.4fr) minmax(140px, 1fr) minmax(120px, 0.8fr);
}
.toolbar-filters :deep(.el-input),
.toolbar-filters :deep(.el-select),
.table-toolbar > :deep(.el-button) {
  width: 100%;
  min-width: 0;
}
.table-shell {
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--card-bg);
}
.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.user-avatar {
  display: grid;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  place-items: center;
  border: 1px solid rgba(64, 158, 255, 0.22);
  border-radius: 8px;
  background: rgba(64, 158, 255, 0.08);
  color: var(--primary-color);
  font-size: 13px;
  font-weight: 700;
}
.user-copy {
  min-width: 0;
}
.user-name {
  overflow: hidden;
  color: var(--text-primary);
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-email {
  overflow: hidden;
  margin-top: 2px;
  color: var(--text-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
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
.action-button:focus-visible {
  background: var(--el-color-primary-light-9);
}
:deep(.operation-column .cell) {
  padding-left: 6px;
  padding-right: 6px;
}
@media (max-width: 768px) {
  .table-toolbar {
    align-items: stretch;
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .toolbar-filters.responsive-filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 480px) {
  .toolbar-filters.responsive-filters {
    grid-template-columns: 1fr;
  }
}
</style>
