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
    <el-table :data="filtered" style="width:100%" v-loading="loading">
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column label="角色" width="120">
        <template #default="{ row }">{{ row.role?.name || '-' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
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
</script>

<style scoped>
.table-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.toolbar-filters { gap: 8px; align-items: center; }
.toolbar-filters.responsive-filters { display: grid; }
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
    flex-direction: column;
    gap: 10px;
  }
  .toolbar-filters { display: grid; }
}
</style>
