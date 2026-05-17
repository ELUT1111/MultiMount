<!--
  挂载管理页面 — 挂载源的增删改查, 3步引导添加, 筛选, 测试连接, 权限管理。
-->
<template>
  <div class="mount-manager">
    <div class="page-header">
      <h2>挂载管理</h2>
      <div class="header-actions">
        <el-select v-model="filterType" placeholder="按类型筛选" clearable style="width: 130px" size="default">
          <el-option v-for="t in mountTypes" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="按状态筛选" clearable style="width: 120px" size="default">
          <el-option label="在线" value="online" />
          <el-option label="离线" value="offline" />
        </el-select>
        <el-button @click="mounts.fetchMounts(true)" :icon="Refresh">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="showAddDialog = true">添加挂载</el-button>
      </div>
    </div>

    <div v-loading="mounts.loading" class="mount-grid">
      <el-empty v-if="!mounts.loading && filteredMounts.length === 0" description="暂无挂载点" />

      <div v-for="mount in filteredMounts" :key="mount.id" class="mount-card">
        <div class="card-header">
          <div class="card-left">
            <el-icon :size="28" color="#409eff"><component :is="typeIcon(mount.type)" /></el-icon>
            <div>
              <div class="mount-name">{{ mount.name }}</div>
              <div class="mount-type">{{ typeLabel(mount.type) }}</div>
            </div>
          </div>
          <div class="card-right">
            <el-tag v-if="mount.my_level" :type="levelTagType(mount.my_level)" size="small" effect="plain">
              {{ levelLabel(mount.my_level) }}
            </el-tag>
            <span class="status-dot" :class="mount.status" :title="statusLabel(mount.status)" />
          </div>
        </div>
        <div class="card-body">
          <div class="info-row"><span>地址:</span> <span>{{ mount.config.host || mount.config.url || mount.config.path || '-' }}{{ mount.config.port ? ':' + mount.config.port : '' }}</span></div>
          <div class="info-row"><span>路径:</span> <span>{{ mount.config.path || mount.config.prefix || '/' }}</span></div>
          <div class="info-row" v-if="mount.owner_name"><span>创建者:</span> <span>{{ mount.owner_name }}</span></div>
          <div class="info-row" v-if="mount.capacity_total"><span>容量:</span> <span>{{ formatSize(mount.capacity_used) }} / {{ formatSize(mount.capacity_total) }}</span></div>
          <div class="info-row" v-if="mount.last_connected_at"><span>最后连接:</span> <span>{{ formatTime(mount.last_connected_at) }}</span></div>
        </div>
        <div class="card-footer">
          <el-button size="small" @click="handleTest(mount)" :loading="testingId === mount.id" v-if="canEdit(mount)">测试连接</el-button>
          <el-button size="small" @click="handleEdit(mount)" v-if="canEdit(mount)">编辑</el-button>
          <el-button size="small" type="warning" plain @click="handleUnmount(mount)" v-if="canEdit(mount)">卸载</el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(mount)" v-if="canEdit(mount)">删除</el-button>
          <el-button size="small" type="primary" plain @click="openPermDialog(mount)" v-if="canManagePerms(mount)">权限管理</el-button>
          <el-button size="small" type="success" plain @click="openRequestDialog(mount)" v-if="mount.my_level === 'none'">申请权限</el-button>
        </div>
      </div>
    </div>

    <!-- 添加/编辑挂载对话框 -->
    <el-dialog v-model="showAddDialog" :title="editMode ? '编辑挂载' : '添加挂载'" width="600px" @close="resetForm">
      <el-steps :active="addStep" finish-status="success" align-center style="margin-bottom: 24px">
        <el-step title="选择类型" />
        <el-step title="配置参数" />
        <el-step title="高级设置" />
      </el-steps>

      <!-- 步骤1: 选择类型 -->
      <div v-if="addStep === 0" class="type-grid">
        <div v-for="t in mountTypes" :key="t.value" class="type-card" :class="{ selected: addForm.type === t.value }" @click="addForm.type = t.value">
          <el-icon :size="32"><component :is="t.icon" /></el-icon>
          <span>{{ t.label }}</span>
        </div>
      </div>

      <!-- 步骤2: 配置参数 -->
      <el-form v-if="addStep === 1" :model="addForm.config" label-width="120px">
        <template v-if="addForm.type === 'local'">
          <el-form-item label="目录路径" required>
            <el-input v-model="addForm.config.path" placeholder="点击右侧按钮选择文件夹">
              <template #append>
                <el-button :icon="FolderOpened" @click="showFolderPicker = true" />
              </template>
            </el-input>
          </el-form-item>
        </template>
        <template v-else-if="addForm.type === 'ftp'">
          <el-form-item label="主机地址" required><el-input v-model="addForm.config.host" /></el-form-item>
          <el-form-item label="端口"><el-input-number v-model="addForm.config.port" :min="1" :max="65535" /></el-form-item>
          <el-form-item label="用户名"><el-input v-model="addForm.config.username" /></el-form-item>
          <el-form-item label="密码"><el-input v-model="addForm.config.password" type="password" show-password /></el-form-item>
          <el-form-item label="被动模式"><el-switch v-model="addForm.config.passive_mode" /></el-form-item>
        </template>
        <template v-else-if="addForm.type === 'sftp'">
          <el-form-item label="主机地址" required><el-input v-model="addForm.config.host" /></el-form-item>
          <el-form-item label="端口"><el-input-number v-model="addForm.config.port" :min="1" :max="65535" /></el-form-item>
          <el-form-item label="用户名" required><el-input v-model="addForm.config.username" /></el-form-item>
          <el-form-item label="密码"><el-input v-model="addForm.config.password" type="password" show-password /></el-form-item>
          <el-form-item label="私钥路径"><el-input v-model="addForm.config.private_key" placeholder="可选" /></el-form-item>
        </template>
        <template v-else-if="addForm.type === 'webdav'">
          <el-form-item label="服务URL" required><el-input v-model="addForm.config.url" placeholder="https://dav.example.com" /></el-form-item>
          <el-form-item label="用户名"><el-input v-model="addForm.config.username" /></el-form-item>
          <el-form-item label="密码"><el-input v-model="addForm.config.password" type="password" show-password /></el-form-item>
          <el-form-item label="忽略SSL"><el-switch v-model="addForm.config.verify_ssl" /></el-form-item>
        </template>
        <template v-else-if="addForm.type === 'oss'">
          <el-form-item label="AccessKey ID" required><el-input v-model="addForm.config.access_key_id" /></el-form-item>
          <el-form-item label="AccessKey Secret" required><el-input v-model="addForm.config.access_key_secret" type="password" show-password /></el-form-item>
          <el-form-item label="Bucket" required><el-input v-model="addForm.config.bucket" /></el-form-item>
          <el-form-item label="Endpoint" required><el-input v-model="addForm.config.endpoint" placeholder="oss-cn-hangzhou.aliyuncs.com" /></el-form-item>
          <el-form-item label="路径前缀"><el-input v-model="addForm.config.prefix" /></el-form-item>
        </template>
        <template v-else-if="addForm.type === 's3'">
          <el-form-item label="AccessKey ID" required><el-input v-model="addForm.config.access_key_id" /></el-form-item>
          <el-form-item label="AccessKey Secret" required><el-input v-model="addForm.config.access_key_secret" type="password" show-password /></el-form-item>
          <el-form-item label="Bucket" required><el-input v-model="addForm.config.bucket" /></el-form-item>
          <el-form-item label="Region"><el-input v-model="addForm.config.region" placeholder="us-east-1" /></el-form-item>
          <el-form-item label="Endpoint"><el-input v-model="addForm.config.endpoint_url" placeholder="可选" /></el-form-item>
          <el-form-item label="路径前缀"><el-input v-model="addForm.config.prefix" /></el-form-item>
        </template>
      </el-form>

      <!-- 步骤3: 高级设置 -->
      <el-form v-if="addStep === 2" :model="addForm" label-width="120px">
        <el-form-item label="挂载名称" required><el-input v-model="addForm.name" /></el-form-item>
        <el-form-item label="缓存过期(秒)"><el-input-number v-model="addForm.advanced_config.cache_ttl" :min="0" /></el-form-item>
        <el-form-item label="连接超时(秒)"><el-input-number v-model="addForm.advanced_config.timeout" :min="5" /></el-form-item>
        <el-form-item label="自动重连"><el-switch v-model="addForm.advanced_config.auto_reconnect" /></el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="addStep > 0 ? addStep-- : showAddDialog = false">{{ addStep > 0 ? '上一步' : '取消' }}</el-button>
        <el-button v-if="addStep === 1" @click="handleTestInModal" :loading="testingInModal">测试连接</el-button>
        <el-button v-if="addStep < 2" type="primary" @click="addStep++" :disabled="addStep === 0 && !addForm.type">下一步</el-button>
        <el-button v-if="addStep === 2" type="primary" :loading="saving" @click="handleSave">{{ editMode ? '更新' : '保存' }}</el-button>
      </template>
    </el-dialog>

    <!-- 权限管理对话框 -->
    <el-dialog v-model="showPermDialog" title="权限管理" width="520px" @close="resetPermDialog">
      <div class="perm-header">
        <span>挂载: <strong>{{ permMount?.name }}</strong></span>
      </div>

      <!-- 已授权用户列表 -->
      <div class="perm-section">
        <div class="perm-section-title">已授权用户</div>
        <div v-if="permLoading" v-loading="true" style="height: 60px" />
        <el-empty v-else-if="permList.length === 0" description="暂无授权用户" :image-size="48" />
        <div v-else class="perm-list">
          <div v-for="p in permList" :key="p.user_id" class="perm-item">
            <div class="perm-user">
              <span class="perm-username">{{ permUserMap[p.user_id] || `用户 #${p.user_id}` }}</span>
              <el-tag :type="p.level === 'readwrite' ? 'success' : 'info'" size="small">{{ levelLabel(p.level) }}</el-tag>
            </div>
            <el-button size="small" type="danger" text @click="handleRevokePerm(p.user_id)">撤销</el-button>
          </div>
        </div>
      </div>

      <!-- 授予新权限 -->
      <el-divider />
      <div class="perm-section">
        <div class="perm-section-title">授予用户权限</div>
        <el-form :inline="true" size="default">
          <el-form-item label="用户">
            <el-select v-model="grantForm.user_id" placeholder="选择用户" filterable style="width: 180px">
              <el-option v-for="u in allUsers" :key="u.id" :label="u.username" :value="u.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="权限">
            <el-select v-model="grantForm.level" style="width: 120px">
              <el-option label="只读" value="read" />
              <el-option label="读写" value="readwrite" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleGrantPerm" :loading="granting">授予</el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-dialog>

    <!-- 申请权限对话框 -->
    <el-dialog v-model="showRequestDialog" title="申请挂载权限" width="420px">
      <p>申请 <strong>{{ requestMount?.name }}</strong> 的访问权限</p>
      <el-form label-width="80px">
        <el-form-item label="权限等级">
          <el-radio-group v-model="requestLevel">
            <el-radio value="read">只读</el-radio>
            <el-radio value="readwrite">读写</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRequestDialog = false">取消</el-button>
        <el-button type="primary" :loading="requesting" @click="handleRequestAccess">发送申请</el-button>
      </template>
    </el-dialog>

    <!-- 文件夹选择器 -->
    <FolderPicker v-model="showFolderPicker" @select="onFolderSelected" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Plus, Refresh, FolderOpened, Connection, Monitor, Cloudy } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMountsStore } from '@/stores/mounts'
import { useAuthStore } from '@/stores/auth'
import { formatSize, formatTime } from '@/utils/format'
import FolderPicker from '@/components/common/FolderPicker.vue'
import { getMountPermissions, grantPermission, revokePermission, requestAccess, getMountRequesters } from '@/api/mount_permissions'
import { listAllUsers } from '@/api/users'

const mounts = useMountsStore()
const auth = useAuthStore()
const route = useRoute()
const showAddDialog = ref(false)
const addStep = ref(0)
const saving = ref(false)
const testingId = ref(null)
const testingInModal = ref(false)
const editMode = ref(false)
const editMountId = ref(null)
const showFolderPicker = ref(false)

// 筛选状态
const filterType = ref('')
const filterStatus = ref('')

// 权限管理状态
const showPermDialog = ref(false)
const permMount = ref(null)
const permList = ref([])
const permLoading = ref(false)
const permUserMap = ref({})
const allUsers = ref([])
const granting = ref(false)
const grantForm = reactive({ user_id: null, level: 'read' })

// 申请权限状态
const showRequestDialog = ref(false)
const requestMount = ref(null)
const requestLevel = ref('read')
const requesting = ref(false)

const mountTypes = [
  { value: 'local', label: '本地文件系统', icon: FolderOpened },
  { value: 'ftp', label: 'FTP', icon: Connection },
  { value: 'sftp', label: 'SFTP', icon: Connection },
  { value: 'webdav', label: 'WebDAV', icon: Monitor },
  { value: 'oss', label: '阿里云 OSS', icon: Cloudy },
  { value: 's3', label: 'Amazon S3', icon: Cloudy },
]

const defaultConfig = () => ({
  type: '', name: '',
  config: { path: '', host: '', port: 21, username: '', password: '', passive_mode: true,
            url: '', verify_ssl: true, private_key: '',
            access_key_id: '', access_key_secret: '', bucket: '', endpoint: '', region: 'us-east-1',
            endpoint_url: '', prefix: '' },
  advanced_config: { cache_ttl: 300, timeout: 30, auto_reconnect: true },
})

const addForm = reactive(defaultConfig())

// 按类型和状态筛选挂载列表
const filteredMounts = computed(() => {
  return mounts.mounts.filter((m) => {
    if (filterType.value && m.type !== filterType.value) return false
    if (filterStatus.value && m.status !== filterStatus.value) return false
    return true
  })
})

const typeIcon = (t) => ({ local: FolderOpened, ftp: Connection, sftp: Connection, webdav: Monitor, oss: Cloudy, s3: Cloudy }[t] || Connection)
const typeLabel = (t) => ({ local: '本地存储', ftp: 'FTP', sftp: 'SFTP', webdav: 'WebDAV', oss: '阿里云 OSS', s3: 'Amazon S3' }[t] || t)
const statusLabel = (s) => ({ online: '在线', offline: '离线', connecting: '连接中' }[s] || s)
const levelLabel = (l) => ({ read: '只读', readwrite: '读写', none: '无权限' }[l] || l)
const levelTagType = (l) => ({ read: 'info', readwrite: 'success', none: 'danger' }[l] || 'info')

// 权限判断
function canEdit(mount) {
  return mount.my_level === 'readwrite'
}

function canManagePerms(mount) {
  return mount.my_level === 'readwrite'
}

async function handleTest(mount) {
  testingId.value = mount.id
  try {
    const res = await mounts.testMount(mount.id)
    ElMessage[res.success ? 'success' : 'error'](res.message)
    mounts.fetchMounts()
  } finally {
    testingId.value = null
  }
}

// 模态框内测试连接（编辑模式下可用）
async function handleTestInModal() {
  if (!editMountId.value) {
    ElMessage.warning('请先保存挂载后再测试连接')
    return
  }
  testingInModal.value = true
  try {
    const { testConnection } = await import('@/api/mounts')
    const res = await testConnection(editMountId.value)
    ElMessage[res.success ? 'success' : 'error'](res.message || '连接测试完成')
  } catch {
    ElMessage.error('连接测试失败')
  } finally {
    testingInModal.value = false
  }
}

// 编辑挂载 — 回填表单
function handleEdit(mount) {
  editMode.value = true
  editMountId.value = mount.id
  addForm.type = mount.type
  addForm.name = mount.name
  Object.assign(addForm.config, mount.config || {})
  Object.assign(addForm.advanced_config, mount.advanced_config || { cache_ttl: 300, timeout: 30, auto_reconnect: true })
  addStep.value = 0
  showAddDialog.value = true
}

// 卸载（软删除）
async function handleUnmount(mount) {
  await ElMessageBox.confirm(`确定卸载 "${mount.name}"?`, '确认', { type: 'warning' })
  await mounts.removeMount(mount.id)
  ElMessage.success('已卸载')
}

// 永久删除
async function handleDelete(mount) {
  await ElMessageBox.confirm(`确定永久删除挂载 "${mount.name}"? 此操作不可恢复。`, '确认删除', { type: 'error' })
  try {
    const { deleteMount } = await import('@/api/mounts')
    await deleteMount(mount.id)
    ElMessage.success('已删除')
    mounts.fetchMounts()
  } catch {
    ElMessage.error('删除失败')
  }
}

// 选择文件夹回调
function onFolderSelected(path) {
  addForm.config.path = path
}

// 重置表单
function resetForm() {
  Object.assign(addForm, defaultConfig())
  addStep.value = 0
  editMode.value = false
  editMountId.value = null
}

async function handleSave() {
  if (!addForm.name.trim()) return ElMessage.warning('请输入挂载名称')
  saving.value = true
  try {
    const payload = {
      name: addForm.name,
      type: addForm.type,
      config: { ...addForm.config },
      advanced_config: { ...addForm.advanced_config },
    }
    if (editMode.value && editMountId.value) {
      const { updateMount } = await import('@/api/mounts')
      await updateMount(editMountId.value, payload)
      ElMessage.success('挂载更新成功')
    } else {
      await mounts.addMount(payload)
      ElMessage.success('挂载创建成功')
    }
    showAddDialog.value = false
    resetForm()
  } finally {
    saving.value = false
  }
}

// ===== 权限管理 =====

async function openPermDialog(mount) {
  permMount.value = mount
  showPermDialog.value = true
  permLoading.value = true
  grantForm.user_id = null
  grantForm.level = 'read'

  try {
    // 管理员可看到所有用户，普通挂载所有者仅看到曾申请过权限的用户
    const usersPromise = auth.isAdmin
      ? listAllUsers()
      : getMountRequesters(mount.id)

    const [perms, users] = await Promise.all([
      getMountPermissions(mount.id),
      usersPromise,
    ])
    permList.value = perms
    allUsers.value = users
    // 构建 user_id → username 映射
    const map = {}
    users.forEach(u => { map[u.id] = u.username })
    permUserMap.value = map
  } catch {
    ElMessage.error('加载权限数据失败')
  } finally {
    permLoading.value = false
  }
}

async function handleGrantPerm() {
  if (!grantForm.user_id) return ElMessage.warning('请选择用户')
  granting.value = true
  try {
    await grantPermission(permMount.value.id, { user_id: grantForm.user_id, level: grantForm.level })
    ElMessage.success('权限已授予')
    grantForm.user_id = null
    // 刷新列表
    permList.value = await getMountPermissions(permMount.value.id)
    mounts.fetchMounts()
  } catch {
    ElMessage.error('授权失败')
  } finally {
    granting.value = false
  }
}

async function handleRevokePerm(userId) {
  await ElMessageBox.confirm('确定撤销该用户的权限？', '确认', { type: 'warning' })
  try {
    await revokePermission(permMount.value.id, userId)
    ElMessage.success('权限已撤销')
    permList.value = await getMountPermissions(permMount.value.id)
    mounts.fetchMounts()
  } catch {
    ElMessage.error('撤销失败')
  }
}

function resetPermDialog() {
  permMount.value = null
  permList.value = []
  permUserMap.value = {}
  grantForm.user_id = null
  grantForm.level = 'read'
}

// ===== 申请权限 =====

function openRequestDialog(mount) {
  requestMount.value = mount
  requestLevel.value = 'read'
  showRequestDialog.value = true
}

async function handleRequestAccess() {
  requesting.value = true
  try {
    await requestAccess(requestMount.value.id, { level: requestLevel.value })
    ElMessage.success('权限申请已发送，请等待挂载所有者审批')
    showRequestDialog.value = false
  } catch {
    ElMessage.error('申请失败')
  } finally {
    requesting.value = false
  }
}

onMounted(async () => {
  await mounts.fetchMounts()
  // 深链接: 从通知跳转时自动打开权限管理对话框
  const openPermsId = Number(route.query.open_perms)
  if (openPermsId) {
    const target = mounts.mounts.find(m => m.id === openPermsId)
    if (target && canManagePerms(target)) {
      openPermDialog(target)
    }
  }
})
</script>

<style scoped>
.mount-manager { display: flex; flex-direction: column; gap: 16px; }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.page-header h2 { font-size: 20px; }
.header-actions { display: flex; gap: 8px; align-items: center; }
.mount-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 16px; }
.mount-card {
  background: var(--card-bg); border-radius: 12px; padding: 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06); transition: box-shadow 0.2s;
}
.mount-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.card-left { display: flex; gap: 12px; align-items: center; }
.card-right { display: flex; align-items: center; gap: 8px; }
.mount-name { font-weight: 600; font-size: 15px; }
.mount-type { font-size: 12px; color: var(--text-secondary); }
/* 彩色状态指示灯 */
.status-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
.status-dot.online { background: var(--success-color); box-shadow: 0 0 6px rgba(103,194,58,0.4); }
.status-dot.offline { background: var(--danger-color); box-shadow: 0 0 6px rgba(245,108,108,0.4); }
.status-dot.connecting { background: var(--warning-color); box-shadow: 0 0 6px rgba(230,162,60,0.4); animation: pulse 1.5s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.card-body { margin-bottom: 12px; }
.info-row { font-size: 13px; color: var(--text-regular); padding: 4px 0; display: flex; gap: 8px; }
.info-row span:first-child { color: var(--text-secondary); min-width: 70px; }
.card-footer { display: flex; gap: 8px; border-top: 1px solid var(--border-color); padding-top: 12px; flex-wrap: wrap; }
.type-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.type-card {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 20px; border: 2px solid var(--border-color); border-radius: 12px;
  cursor: pointer; transition: all 0.2s;
}
.type-card:hover { border-color: var(--primary-color); background: rgba(64,158,255,0.04); }
.type-card.selected { border-color: var(--primary-color); background: rgba(64,158,255,0.08); }

/* 权限管理对话框 */
.perm-header { margin-bottom: 16px; font-size: 14px; }
.perm-section { margin-bottom: 8px; }
.perm-section-title { font-weight: 600; font-size: 14px; margin-bottom: 8px; }
.perm-list { display: flex; flex-direction: column; gap: 8px; }
.perm-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--bg-color); border-radius: 8px; }
.perm-user { display: flex; align-items: center; gap: 8px; }
.perm-username { font-size: 14px; }
</style>
