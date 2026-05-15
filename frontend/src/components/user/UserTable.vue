<!--
  用户表格组件 — 展示用户列表, 支持搜索/角色/状态筛选和编辑/禁用/删除操作。
-->
<template>
  <div class="user-table">
    <div class="table-toolbar">
      <div class="toolbar-filters">
        <el-input v-model="search" placeholder="搜索用户名/邮箱..." :prefix-icon="Search" clearable style="width:200px" />
        <el-select v-model="filterRole" placeholder="角色" clearable style="width:120px">
          <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.name" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="状态" clearable style="width:100px">
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
      <el-table-column label="最后登录" width="170">
        <template #default="{ row }">{{ formatTime(row.last_login_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="$emit('edit', row)">编辑</el-button>
          <el-button link :type="row.is_active ? 'warning' : 'success'" size="small" @click="$emit('toggle', row)">
            {{ row.is_active ? '禁用' : '启用' }}
          </el-button>
          <el-button link type="danger" size="small" @click="$emit('delete', row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Plus, Search } from '@element-plus/icons-vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { formatTime } from '@/utils/format'

const props = defineProps({
  users: { type: Array, default: () => [] },
  roles: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

defineEmits(['add', 'edit', 'toggle', 'delete'])

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
</script>

<style scoped>
.table-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.toolbar-filters { display: flex; gap: 8px; align-items: center; }
</style>
