<!--
  用户与权限管理页面 — 用户 CRUD + 角色权限配置 + 挂载点权限 + QoS 限制。
  使用 UserTable/UserForm/RolePermission 子组件拆分职责。
-->
<template>
  <div class="user-manager">
    <div class="page-header">
      <div class="header-copy">
        <h2>用户与权限管理</h2>
        <div class="header-meta">
          <span>{{ users.length }} 个用户</span>
          <span>{{ activeUserCount }} 个启用</span>
          <span>{{ roles.length }} 个角色</span>
        </div>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="manager-tabs">
      <!-- 用户管理 -->
      <el-tab-pane label="用户管理" name="users">
        <UserTable :users="users" :roles="roles" :loading="loading"
          @add="showUserDialog = true; editUser = null"
          @edit="handleEditUser" @toggle="toggleUser" @delete="handleDeleteUser" />
      </el-tab-pane>

      <!-- 角色与权限 -->
      <el-tab-pane label="角色与权限" name="roles">
        <div class="roles-layout">
          <div class="role-list">
            <div class="role-list-header">
              <span>角色列表</span>
              <el-button type="primary" size="small" :icon="Plus" @click="handleNewRole">新建</el-button>
            </div>
            <div v-for="role in roles" :key="role.id" class="role-item"
              :class="{ active: selectedRole?.id === role.id }"
              @click="selectedRole = role">
              <div class="role-copy">
                <span class="role-name">{{ role.name }}</span>
                <span class="role-desc">{{ role.description || '无描述' }}</span>
              </div>
            </div>
            <el-empty v-if="roles.length === 0" description="暂无角色" :image-size="48" />
          </div>
          <div class="role-detail">
            <RolePermission :role="selectedRole" :mounts="mounts.mounts"
              @save="handleSaveRole" @reset="handleResetRole" />
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 用户表单对话框 -->
    <UserForm v-model="showUserDialog" :edit-user="editUser" :roles="roles" @submit="handleSaveUser" />
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listUsers, createUser, deleteUser, updateUser, listRoles, updateRole, createRole } from '@/api/users'
import { useMountsStore } from '@/stores/mounts'
import UserTable from '@/components/user/UserTable.vue'
import UserForm from '@/components/user/UserForm.vue'
import RolePermission from '@/components/user/RolePermission.vue'

const mounts = useMountsStore()
const activeTab = ref('users')
const users = ref([])
const roles = ref([])
const loading = ref(false)
const selectedRole = ref(null)
const showUserDialog = ref(false)
const editUser = ref(null)

const activeUserCount = computed(() => users.value.filter((user) => user.is_active).length)

async function fetchUsers() {
  loading.value = true
  try { users.value = (await listUsers({ page: 1, page_size: 100 })).items } catch {} finally { loading.value = false }
}

async function fetchRoles() {
  try { roles.value = await listRoles() } catch {}
}

function handleEditUser(user) {
  editUser.value = user
  showUserDialog.value = true
}

async function handleSaveUser({ isEdit, userId, payload }) {
  try {
    if (isEdit) {
      const updatePayload = { email: payload.email, role_id: payload.role_id }
      if (payload.password) updatePayload.password = payload.password
      await updateUser(userId, updatePayload)
      ElMessage.success('用户更新成功')
    } else {
      await createUser(payload)
      ElMessage.success('用户创建成功')
    }
    showUserDialog.value = false
    fetchUsers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function toggleUser(user) {
  try {
    await updateUser(user.id, { is_active: !user.is_active })
    ElMessage.success(user.is_active ? '已禁用' : '已启用')
    fetchUsers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleDeleteUser(user) {
  await ElMessageBox.confirm(`确定删除用户 "${user.username}"?`, '确认', { type: 'warning' })
  try {
    await deleteUser(user.id)
    ElMessage.success('已删除')
    fetchUsers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function handleNewRole() {
  const { value } = await ElMessageBox.prompt('请输入角色名称', '新建角色', {
    inputValidator: (v) => !!v.trim() || '名称不能为空',
  })
  try {
    await createRole({
      name: value.trim(),
      description: '',
      permissions: { can_login: true, can_upload: true, can_download: true, can_modify: false, can_delete: false },
      qos_limits: { max_download_kbps: 0, max_upload_kbps: 0, max_concurrent: 5 },
      mount_permissions: {},
    })
    ElMessage.success('角色创建成功')
    fetchRoles()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  }
}

function handleResetRole() {
  if (!selectedRole.value) return
  const original = roles.value.find((r) => r.id === selectedRole.value.id)
  if (original) selectedRole.value = { ...original }
}

async function handleSaveRole(roleData) {
  try {
    await updateRole(roleData.id, {
      permissions: roleData.permissions,
      qos_limits: roleData.qos_limits,
      mount_permissions: roleData.mount_permissions,
    })
    ElMessage.success('角色配置已保存')
    fetchRoles()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

onMounted(() => { fetchUsers(); fetchRoles(); mounts.fetchMounts() })
</script>

<style scoped>
.user-manager {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.page-header {
  display: grid;
  grid-template-columns: minmax(220px, 1fr);
  gap: 16px;
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
.manager-tabs {
  min-width: 0;
}
.roles-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
  min-height: 480px;
}
.role-list {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--card-bg);
}
.role-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding-bottom: 4px;
  font-weight: 700;
  font-size: 14px;
}
.role-item {
  display: flex;
  min-width: 0;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}
.role-item:hover {
  background: rgba(64, 158, 255, 0.06);
}
.role-item.active {
  border-color: rgba(64, 158, 255, 0.32);
  background: rgba(64, 158, 255, 0.1);
  color: var(--primary-color);
}
.role-copy {
  min-width: 0;
}
.role-name {
  display: block;
  overflow: hidden;
  color: var(--text-primary);
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.role-item.active .role-name {
  color: var(--primary-color);
}
.role-desc {
  display: block;
  overflow: hidden;
  margin-top: 3px;
  color: var(--text-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.role-detail {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--card-bg);
}

@media (max-width: 1024px) {
  .roles-layout {
    grid-template-columns: 1fr;
  }
  .role-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    align-items: stretch;
  }
  .role-list-header {
    grid-column: 1 / -1;
  }
}

@media (max-width: 768px) {
  .user-manager {
    gap: 14px;
  }
  .page-header h2 {
    font-size: 20px;
  }
  .role-list {
    grid-template-columns: 1fr;
  }
}
</style>
