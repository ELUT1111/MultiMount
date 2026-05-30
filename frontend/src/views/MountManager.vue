<!--
  挂载管理页面 — 挂载源的增删改查, 3步引导添加, 筛选, 测试连接, 权限管理。
-->
<template>
  <div class="mount-manager">
    <PageHeader
      title="挂载管理"
      :meta="[
        `${filteredMounts.length} / ${mounts.mounts.length} 个挂载`,
        `${onlineMountCount} 个在线`,
      ]"
    >
      <template #actions>
        <el-select v-model="filterType" placeholder="按类型筛选" clearable size="default">
          <el-option v-for="t in mountTypes" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="按状态筛选" clearable size="default">
          <el-option label="在线" value="online" />
          <el-option label="离线" value="offline" />
        </el-select>
        <el-button @click="mounts.fetchMounts(true)" :icon="Refresh">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="showAddDialog = true">添加挂载</el-button>
      </template>
    </PageHeader>

    <div v-loading="mounts.loading" class="mount-grid">
      <el-empty v-if="!mounts.loading && filteredMounts.length === 0" class="mount-empty" description="暂无挂载点" />

      <div v-for="mount in filteredMounts" :key="mount.id" class="mount-card">
        <div class="mount-card-top">
          <div class="card-left">
            <div class="mount-icon">
              <el-icon :size="24"><component :is="typeIcon(mount.type)" /></el-icon>
            </div>
            <div class="mount-title-block">
              <div class="mount-name">{{ mount.name }}</div>
              <div class="mount-type">{{ typeLabel(mount.type) }}</div>
            </div>
          </div>
          <div class="mount-badges">
            <el-tag v-if="mount.my_level" :type="levelTagType(mount.my_level)" size="small" effect="plain">
              {{ levelLabel(mount.my_level) }}
            </el-tag>
            <el-tag :type="statusTagType(mount.status)" size="small" effect="plain" class="status-tag">
              <span class="status-dot" :class="mount.status" />
              {{ statusLabel(mount.status) }}
            </el-tag>
          </div>
        </div>
        <div class="card-body">
          <div class="mount-meta-grid">
            <div class="info-row">
              <span>地址</span>
              <strong :title="mountEndpoint(mount)">{{ mountEndpoint(mount) }}</strong>
            </div>
            <div class="info-row">
              <span>路径</span>
              <strong :title="mountPath(mount)">{{ mountPath(mount) }}</strong>
            </div>
            <div class="info-row" v-if="mount.owner_name">
              <span>创建者</span>
              <strong>{{ mount.owner_name }}</strong>
            </div>
            <div class="info-row" v-if="mount.last_connected_at">
              <span>最后连接</span>
              <strong>{{ formatTime(mount.last_connected_at) }}</strong>
            </div>
          </div>
          <div class="capacity-meter" v-if="hasFileStats(mount)">
            <div class="capacity-copy">
              <span>文件数量</span>
              <strong>{{ formatFileCount(mount.capacity_used) }}</strong>
            </div>
            <div class="capacity-copy">
              <span>总大小</span>
              <strong>{{ formatSize(mount.capacity_total || 0) }}</strong>
            </div>
          </div>
        </div>
        <div class="card-footer">
          <el-button
            size="small"
            class="card-action action-test"
            :icon="Refresh"
            @click="handleTest(mount)"
            :loading="testingId === mount.id"
            v-if="canTest(mount)"
          >
            测试连接
          </el-button>
          <el-button size="small" class="card-action action-edit" :icon="Edit" @click="handleEdit(mount)" v-if="canEdit(mount)">编辑</el-button>
          <el-button size="small" class="card-action action-request" :icon="Key" @click="openRequestDialog(mount)" v-if="mount.my_level === 'none'">申请权限</el-button>
          <el-dropdown v-if="canEdit(mount) || canManagePerms(mount)" trigger="click">
            <el-button size="small" class="card-action action-more" :icon="MoreFilled">更多</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="canManagePerms(mount)" :icon="Key" @click="openPermDialog(mount)">权限管理</el-dropdown-item>
                <el-dropdown-item v-if="canEdit(mount)" :icon="Delete" class="danger-action" divided @click="handleDelete(mount)">删除挂载</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>

    <!-- 添加/编辑挂载对话框 -->
    <el-dialog v-model="showAddDialog" :title="editMode ? '编辑挂载' : '添加挂载'" class="responsive-dialog mount-dialog" @close="resetForm">
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
        <template v-if="addForm.type === 'managed'">
          <el-alert
            type="success"
            show-icon
            :closable="false"
            title="新建空挂载点"
            class="local-mount-hint"
          />
          <div class="managed-mount-preview">
            <span>目录名称</span>
            <strong>{{ addForm.name || '下一步填写挂载名称后生成' }}</strong>
          </div>
        </template>
        <template v-else-if="addForm.type === 'local'">
          <el-alert
            type="info"
            show-icon
            :closable="false"
            title="此处选择的是服务器上的本地文件夹，不是浏览器所在电脑的文件夹。"
            class="local-mount-hint"
          />
          <el-form-item label="目录路径" required>
            <el-input v-model="addForm.config.path" placeholder="选择服务器上的目录路径">
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
        <el-button v-if="addStep === 1 && editMode && canTestEditingMount" @click="handleTestInModal" :loading="testingInModal">测试连接</el-button>
        <el-button v-if="addStep < 2" type="primary" @click="handleNextStep" :disabled="addStep === 0 && !addForm.type">下一步</el-button>
        <el-button v-if="addStep === 2" type="primary" :loading="saving" @click="handleSave">{{ editMode ? '更新' : '保存' }}</el-button>
      </template>
    </el-dialog>

    <!-- 权限管理对话框 -->
    <el-dialog v-model="showPermDialog" title="权限管理" class="responsive-dialog perm-dialog" @close="resetPermDialog">
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
            <el-select v-model="grantForm.user_id" placeholder="选择用户" filterable>
              <el-option v-for="u in allUsers" :key="u.id" :label="u.username" :value="u.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="权限">
            <el-select v-model="grantForm.level">
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
    <el-dialog v-model="showRequestDialog" title="申请挂载权限" class="responsive-dialog request-dialog">
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
import { Plus, Refresh, FolderOpened, Connection, Monitor, Cloudy, Edit, Delete, Key, MoreFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMountsStore } from '@/stores/mounts'
import { useAuthStore } from '@/stores/auth'
import { formatSize, formatTime } from '@/utils/format'
import FolderPicker from '@/components/common/FolderPicker.vue'
import PageHeader from '@/components/common/PageHeader.vue'
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
const testResults = reactive({})
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

const allMountTypes = [
  { value: 'managed', label: '挂载点', icon: FolderOpened },
  { value: 'local', label: '服务器本地文件系统', icon: FolderOpened },
  { value: 'ftp', label: 'FTP', icon: Connection },
  { value: 'sftp', label: 'SFTP', icon: Connection },
  { value: 'webdav', label: 'WebDAV', icon: Monitor },
  { value: 'oss', label: '阿里云 OSS', icon: Cloudy },
  { value: 's3', label: 'Amazon S3', icon: Cloudy },
]

const mountTypes = computed(() => allMountTypes.filter((type) => auth.isAdmin || type.value !== 'local'))

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

const onlineMountCount = computed(() => mounts.mounts.filter((m) => m.status === 'online').length)

const typeIcon = (t) => ({ managed: FolderOpened, local: FolderOpened, ftp: Connection, sftp: Connection, webdav: Monitor, oss: Cloudy, s3: Cloudy }[t] || Connection)
const typeLabel = (t) => ({ managed: '挂载点', local: '服务器本地存储', ftp: 'FTP', sftp: 'SFTP', webdav: 'WebDAV', oss: '阿里云 OSS', s3: 'Amazon S3' }[t] || t)
const statusLabel = (s) => ({ online: '在线', offline: '离线', connecting: '连接中' }[s] || s)
const statusTagType = (s) => ({ online: 'success', offline: 'danger', connecting: 'warning' }[s] || 'info')
const levelLabel = (l) => ({ read: '只读', readwrite: '读写', none: '无权限' }[l] || l)
const levelTagType = (l) => ({ read: 'info', readwrite: 'success', none: 'danger' }[l] || 'info')

function mountEndpoint(mount) {
  const cfg = mount.config || {}
  if (mount.type === 'managed') return 'MountHub 托管目录'
  const base = cfg.host || cfg.url || cfg.path || cfg.bucket || '-'
  return cfg.port ? `${base}:${cfg.port}` : base
}

function mountPath(mount) {
  const cfg = mount.config || {}
  if (mount.type === 'managed') return cfg.directory_name || cfg.path || '/'
  return cfg.path || cfg.prefix || cfg.endpoint || cfg.endpoint_url || '/'
}

function hasFileStats(mount) {
  return mount.capacity_used != null || mount.capacity_total != null
}

function formatFileCount(value) {
  return `${Number(value) || 0} 个`
}

// 权限判断
function isOwner(mount) {
  return mount.user_id === auth.user?.id
}

function canTest(mount) {
  return isOwner(mount)
}

function canEdit(mount) {
  return auth.isAdmin || isOwner(mount)
}

function canManagePerms(mount) {
  return auth.isAdmin || isOwner(mount)
}

function testIndicatorClass(mount) {
  const lastResult = testResults[mount.id]
  if (lastResult === true) return 'is-success'
  if (lastResult === false) return 'is-failed'
  return mount.status === 'online' ? 'is-success' : 'is-failed'
}

const canTestEditingMount = computed(() => {
  if (!editMountId.value) return false
  const mount = mounts.mounts.find((m) => m.id === editMountId.value)
  return mount ? canTest(mount) : false
})

async function handleTest(mount) {
  testingId.value = mount.id
  try {
    const res = await mounts.testMount(mount.id)
    testResults[mount.id] = Boolean(res.success)
    ElMessage[res.success ? 'success' : 'error'](res.message)
  } catch {
    testResults[mount.id] = false
    ElMessage.error('连接测试失败')
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
    const res = await mounts.testMount(editMountId.value)
    ElMessage[res.success ? 'success' : 'error'](res.message || '连接测试完成')
  } catch {
    ElMessage.error('连接测试失败')
  } finally {
    testingInModal.value = false
  }
}

function validateCurrentStep() {
  if (addStep.value === 0) {
    if (!addForm.type) {
      ElMessage.warning('请选择挂载类型')
      return false
    }
    return true
  }

  if (addStep.value === 1) {
    const cfg = addForm.config
    const requiredByType = {
      local: [['path', '请选择目录路径']],
      ftp: [['host', '请输入主机地址']],
      sftp: [['host', '请输入主机地址'], ['username', '请输入用户名']],
      webdav: [['url', '请输入 WebDAV 服务 URL']],
      oss: [
        ['access_key_id', '请输入 AccessKey ID'],
        ['access_key_secret', '请输入 AccessKey Secret'],
        ['bucket', '请输入 Bucket'],
        ['endpoint', '请输入 Endpoint'],
      ],
      s3: [
        ['access_key_id', '请输入 AccessKey ID'],
        ['access_key_secret', '请输入 AccessKey Secret'],
        ['bucket', '请输入 Bucket'],
      ],
    }
    for (const [key, message] of requiredByType[addForm.type] || []) {
      if (!String(cfg[key] ?? '').trim()) {
        ElMessage.warning(message)
        return false
      }
    }
  }
  return true
}

function handleNextStep() {
  if (!validateCurrentStep()) return
  addStep.value++
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

// 永久删除
async function handleDelete(mount) {
  await ElMessageBox.confirm(`确定永久删除挂载 "${mount.name}"? 此操作不可恢复。`, '确认删除', { type: 'error' })
  try {
    await mounts.removeMount(mount.id)
    ElMessage.success('已删除')
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
  if (!validateCurrentStep()) return
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
      const mount = await mounts.addMount(payload)
      ElMessage.success('挂载创建成功，正在测试连接')
      const res = await mounts.testMount(mount.id)
      testResults[mount.id] = Boolean(res.success)
      ElMessage[res.success ? 'success' : 'warning'](res.message || (res.success ? '连接成功' : '连接失败'))
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
    mounts.fetchMounts(true)
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
    mounts.fetchMounts(true)
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
.mount-manager {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.mount-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(360px, 100%), 1fr));
  gap: 16px;
  align-items: stretch;
}

.mount-empty {
  grid-column: 1 / -1;
  min-height: 280px;
  border: 1px dashed var(--border-color);
  border-radius: 8px;
  background: var(--card-bg);
}

.mount-card {
  display: flex;
  min-width: 0;
  min-height: 292px;
  flex-direction: column;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 18px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.mount-card:hover {
  border-color: rgba(64, 158, 255, 0.45);
  box-shadow: 0 8px 22px rgba(31, 45, 61, 0.08);
  transform: translateY(-1px);
}

.mount-card-top {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border-color);
}

.card-left {
  display: flex;
  min-width: 0;
  gap: 12px;
  align-items: center;
}

.mount-icon {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  place-items: center;
  border: 1px solid rgba(64, 158, 255, 0.22);
  border-radius: 8px;
  color: var(--primary-color);
  background: rgba(64, 158, 255, 0.08);
}

.mount-title-block {
  min-width: 0;
}

.mount-name {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 700;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mount-type {
  overflow: hidden;
  margin-top: 2px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mount-badges {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
  max-width: 156px;
}

.status-tag :deep(.el-tag__content) {
  display: inline-flex;
  gap: 5px;
  align-items: center;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.online {
  background: var(--success-color);
}

.status-dot.offline {
  background: var(--danger-color);
}

.status-dot.connecting {
  background: var(--warning-color);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}

.card-body {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 14px;
  padding: 14px 0;
}

.mount-meta-grid {
  display: grid;
  gap: 10px;
}

.info-row {
  display: grid;
  min-width: 0;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 12px;
  align-items: baseline;
  color: var(--text-regular);
  font-size: 13px;
  line-height: 1.35;
}

.info-row span {
  color: var(--text-secondary);
}

.info-row strong {
  overflow: hidden;
  color: var(--text-regular);
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.capacity-meter {
  display: grid;
  gap: 8px;
  margin-top: auto;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--bg-color);
}

.capacity-copy {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}

.capacity-copy strong {
  overflow: hidden;
  color: var(--text-regular);
  font-weight: 600;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-footer {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
  border-top: 1px solid var(--border-color);
  padding-top: 14px;
  flex-wrap: wrap;
}

.card-footer :deep(.el-button + .el-button) {
  margin-left: 0;
}

.card-action {
  height: 32px;
  border-radius: 8px;
  font-weight: 600;
  letter-spacing: 0;
}

.action-test {
  color: var(--success-color);
  background: rgba(103, 194, 58, 0.08);
  border-color: rgba(103, 194, 58, 0.28);
}

.action-edit {
  color: var(--primary-color);
  background: rgba(64, 158, 255, 0.08);
  border-color: rgba(64, 158, 255, 0.28);
}

.action-request {
  color: var(--warning-color);
  background: rgba(230, 162, 60, 0.1);
  border-color: rgba(230, 162, 60, 0.32);
}

.action-more {
  color: var(--text-regular);
  background: var(--bg-color);
  border-color: var(--border-color);
}

.type-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.type-card {
  display: flex;
  min-height: 112px;
  min-width: 0;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 16px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  text-align: center;
  transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}

.type-card span {
  max-width: 100%;
  overflow-wrap: anywhere;
  color: var(--text-regular);
  font-size: 13px;
  line-height: 1.35;
}

.type-card:hover {
  border-color: var(--primary-color);
  background: rgba(64, 158, 255, 0.04);
}

.type-card.selected {
  border-color: var(--primary-color);
  color: var(--primary-color);
  background: rgba(64, 158, 255, 0.08);
}

.type-card.selected span {
  color: var(--primary-color);
  font-weight: 600;
}
.local-mount-hint {
  margin-bottom: 12px;
}
.managed-mount-preview {
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px solid color-mix(in srgb, var(--success-color) 24%, var(--border-color));
  border-radius: 8px;
  background: color-mix(in srgb, var(--success-color) 8%, transparent);
}
.managed-mount-preview span {
  color: var(--text-secondary);
  font-size: 12px;
}
.managed-mount-preview strong {
  color: var(--text-primary);
  font-size: 14px;
  overflow-wrap: anywhere;
}

:deep(.mount-dialog .el-steps) {
  margin-bottom: 22px !important;
}

:deep(.mount-dialog .el-form),
:deep(.request-dialog .el-form) {
  max-width: 100%;
}

:deep(.mount-dialog .el-input-number) {
  width: 180px;
}

.perm-header {
  margin-bottom: 16px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-color);
  padding: 10px 12px;
  color: var(--text-regular);
  font-size: 14px;
}

.perm-section {
  margin-bottom: 8px;
}

.perm-section-title {
  margin-bottom: 10px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
}

.perm-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.perm-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--card-bg);
}

.perm-user {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
}

.perm-username {
  overflow: hidden;
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.perm-dialog .el-form--inline) {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) 140px auto;
  gap: 10px;
  align-items: end;
}

:deep(.perm-dialog .el-form--inline .el-form-item) {
  margin-right: 0;
  margin-bottom: 0;
}

:deep(.perm-dialog .el-select),
:deep(.perm-dialog .el-button) {
  width: 100%;
}

@media (max-width: 768px) {
  .mount-manager {
    gap: 14px;
  }

  .mount-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .mount-card {
    min-height: 0;
    padding: 14px;
  }

  .mount-card-top {
    gap: 10px;
  }

  .mount-badges {
    max-width: 132px;
  }

  .info-row {
    grid-template-columns: 64px minmax(0, 1fr);
  }

  .card-footer {
    justify-content: stretch;
  }

  .card-footer > :deep(.el-button),
  .card-footer > :deep(.el-dropdown) {
    flex: 1 1 calc(50% - 4px);
  }

  .card-footer :deep(.el-dropdown .el-button) {
    width: 100%;
  }

  .type-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .type-card {
    min-height: 96px;
    padding: 14px 8px;
  }

  :deep(.mount-dialog .el-form-item),
  :deep(.request-dialog .el-form-item) {
    display: block;
  }

  :deep(.mount-dialog .el-form-item__label),
  :deep(.request-dialog .el-form-item__label) {
    justify-content: flex-start;
    margin-bottom: 4px;
  }

  :deep(.mount-dialog .el-input-number) {
    width: 100%;
  }

  :deep(.perm-dialog .el-form--inline) {
    grid-template-columns: 1fr;
  }

  .perm-item {
    align-items: flex-start;
  }
}

@media (max-width: 480px) {
  .type-grid {
    grid-template-columns: 1fr;
  }

  .mount-card-top {
    flex-direction: column;
  }

  .mount-badges {
    justify-content: flex-start;
    max-width: 100%;
  }

  .card-footer > :deep(.el-button),
  .card-footer > :deep(.el-dropdown) {
    flex-basis: 100%;
  }
}
</style>
