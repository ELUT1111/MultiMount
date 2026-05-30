<template>
  <aside class="side-panel" :class="{ compact, collapsed }">
    <nav class="nav-menu">
      <div v-for="item in menuItems" :key="item.path"
           class="nav-item" :class="{ active: currentPath === item.path }"
           @click="$router.push(item.path)">
        <el-icon :size="18"><component :is="item.icon" /></el-icon>
        <span class="nav-label">{{ item.label }}</span>
      </div>
    </nav>

    <el-divider class="mount-divider" />

    <div class="section-title mount-section">已挂载资源</div>
    <div class="mount-list mount-section">
      <!-- 按挂载类型分组显示 -->
      <template v-for="group in groupedMounts" :key="group.type">
        <div class="group-label">{{ group.label }}</div>
        <div v-for="mount in group.items" :key="mount.id" class="mount-item"
             :class="{ active: files.currentMountId === mount.id }"
             @click="files.fetchFiles(mount.id, '/')">
          <span class="status-dot" :class="mount.status === 'online' ? 'online' : 'offline'" />
          <el-icon :size="14"><component :is="mountTypeIcon(mount.type)" /></el-icon>
          <span class="mount-name">{{ mount.name }}</span>
        </div>
      </template>
      <div v-if="mounts.accessibleMounts.length === 0" class="empty-hint">暂无可访问挂载</div>
    </div>

    <div class="sidebar-bottom mount-section">
      <div class="webdav-toggle" v-if="auth.isAdmin">
        <span class="webdav-label">WebDAV 服务</span>
        <el-switch v-model="webdavRunning" size="small" :loading="webdavLoading" @change="toggleWebDAV" />
      </div>
      <el-button
        type="primary"
        size="small"
        plain
        style="width:100%"
        :loading="testingOwnMounts"
        :disabled="ownMounts.length === 0"
        @click="testOwnMounts"
      >
        <el-icon><Connection /></el-icon>快速测试连接
      </el-button>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Delete, FolderOpened, Connection, User, Upload, Setting, Monitor, Cloudy, DataLine, Share } from '@element-plus/icons-vue'
import { useMountsStore } from '@/stores/mounts'
import { useFilesStore } from '@/stores/files'
import { useAuthStore } from '@/stores/auth'
import { getWebDAVStatus, startWebDAV, stopWebDAV } from '@/api/webdav'

defineProps({
  compact: { type: Boolean, default: false },
  collapsed: { type: Boolean, default: false },
})

const route = useRoute()
const mounts = useMountsStore()
const files = useFilesStore()
const auth = useAuthStore()
const webdavRunning = ref(false)
const webdavLoading = ref(false)
const testingOwnMounts = ref(false)
const currentPath = computed(() => route.path)

// 所有菜单项 (adminOnly 标记的仅管理员可见)
const allMenuItems = [
  { path: '/files', label: '文件浏览器', icon: FolderOpened },
  { path: '/mounts', label: '挂载管理', icon: Connection },
  { path: '/transfers', label: '传输任务', icon: Upload },
  { path: '/shares', label: '分享链接', icon: Share },
  { path: '/trash', label: '回收站', icon: Delete },
  { path: '/users', label: '用户与权限', icon: User, adminOnly: true },
  { path: '/settings', label: '系统设置', icon: Setting, adminOnly: true },
  { path: '/monitor', label: '请求监控', icon: DataLine, adminOnly: true },
]

// 根据管理员身份过滤菜单
const menuItems = computed(() =>
  auth.isAdmin ? allMenuItems : allMenuItems.filter((i) => !i.adminOnly)
)

const iconMap = { managed: FolderOpened, local: FolderOpened, ftp: Connection, sftp: Connection, webdav: Monitor, oss: Cloudy, s3: Cloudy }
function mountTypeIcon(type) { return iconMap[type] || Connection }

// 按类型分组挂载资源
const typeOrder = ['managed', 'local', 'ftp', 'sftp', 'webdav', 'oss', 's3']
const typeLabels = { managed: '挂载点', local: '服务器本地存储', ftp: 'FTP', sftp: 'SFTP', webdav: 'WebDAV', oss: '阿里云 OSS', s3: 'Amazon S3' }
const groupedMounts = computed(() => {
  const map = {}
  for (const m of mounts.accessibleMounts) {
    if (!map[m.type]) map[m.type] = []
    map[m.type].push(m)
  }
  return typeOrder.filter((t) => map[t]).map((t) => ({ type: t, label: typeLabels[t] || t, items: map[t] }))
})

const ownMounts = computed(() => {
  const userId = auth.user?.id
  if (!userId) return []
  return mounts.mounts.filter((m) => m.user_id === userId)
})

async function testOwnMounts() {
  if (testingOwnMounts.value) return

  if (!mounts.loaded) {
    await mounts.fetchMounts()
  }

  if (ownMounts.value.length === 0) {
    ElMessage.warning('暂无自己的挂载点可测试')
    return
  }

  testingOwnMounts.value = true
  try {
    const results = await Promise.allSettled(
      ownMounts.value.map(async (mount) => {
        const result = await mounts.testMount(mount.id)
        return { mount, result }
      })
    )
    const successCount = results.filter((item) => item.status === 'fulfilled' && item.value.result.success).length
    const failedCount = results.length - successCount

    if (failedCount === 0) {
      ElMessage.success(`已完成 ${successCount} 个挂载点测试，全部连接成功`)
    } else {
      ElMessage.warning(`已完成 ${results.length} 个挂载点测试，成功 ${successCount} 个，失败 ${failedCount} 个`)
    }
  } finally {
    testingOwnMounts.value = false
  }
}

async function toggleWebDAV(running) {
  webdavLoading.value = true
  try {
    if (running) {
      await startWebDAV()
      ElMessage.success('WebDAV 服务已启动')
    } else {
      await stopWebDAV()
      ElMessage.success('WebDAV 服务已停止')
    }
  } catch {
    webdavRunning.value = !running // 回滚状态
    ElMessage.error('WebDAV 操作失败')
  } finally {
    webdavLoading.value = false
  }
}

onMounted(async () => {
  mounts.fetchMounts()
  // 获取 WebDAV 服务状态 (仅管理员)
  if (auth.isAdmin) {
    try {
      const status = await getWebDAVStatus()
      webdavRunning.value = status.running
    } catch {
      // 静默失败
    }
  }
})
</script>

<style scoped>
.side-panel {
  width: 100%;
  height: 100%;
  background: var(--card-bg);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  padding: 12px;
  overflow-y: auto;
  overflow-x: hidden;
  transition: padding 0.18s ease, opacity 0.12s ease;
}
.nav-menu { display: flex; flex-direction: column; gap: 4px; }
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 8px;
  cursor: pointer; color: var(--text-regular); font-size: 14px;
  transition: all 0.2s;
}
.nav-item:hover { background: rgba(64, 158, 255, 0.08); color: var(--primary-color); }
.nav-item.active { background: rgba(64, 158, 255, 0.12); color: var(--primary-color); font-weight: 600; }
.nav-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.section-title { font-size: 12px; color: var(--text-secondary); padding: 8px 12px 4px; }
.mount-list { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.mount-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; border-radius: 6px; font-size: 13px; color: var(--text-regular);
}
.mount-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot.online { background: var(--success-color); }
.status-dot.offline { background: var(--danger-color); }
.empty-hint { font-size: 12px; color: var(--text-secondary); padding: 8px 12px; }
.group-label { font-size: 11px; color: var(--text-secondary); padding: 8px 12px 2px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
.mount-item.active { background: rgba(64, 158, 255, 0.12); color: var(--primary-color); }
.sidebar-bottom { margin-top: auto; padding-top: 12px; border-top: 1px solid var(--border-color); }
.webdav-toggle {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 0; font-size: 13px; color: var(--text-regular);
}
.side-panel.compact {
  padding: 10px 8px;
}
.side-panel.compact .nav-item {
  justify-content: center;
  gap: 0;
  padding: 10px 6px;
}
.side-panel.compact .nav-label,
.side-panel.compact .mount-section,
.side-panel.compact .mount-divider {
  display: none;
}
.side-panel.collapsed {
  padding: 0;
  opacity: 0;
  pointer-events: none;
  border-right: none;
}

@media (max-width: 768px) {
  .side-panel {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 1000;
    width: auto;
    height: var(--mobile-nav-height);
    border-right: none;
    border-top: 1px solid var(--border-color);
    padding: 6px 8px;
    overflow: visible;
    opacity: 1;
    pointer-events: auto;
  }
  .nav-menu {
    height: 100%;
    flex-direction: row;
    justify-content: space-around;
    gap: 2px;
  }
  .nav-item {
    flex: 1;
    min-width: 0;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
    padding: 5px 2px;
    font-size: 11px;
    border-radius: 6px;
  }
  .nav-item :deep(.el-icon) { font-size: 17px; }
  .mount-section,
  .mount-divider {
    display: none;
  }
}
</style>
