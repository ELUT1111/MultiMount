<template>
  <aside class="side-panel">
    <nav class="nav-menu">
      <div v-for="item in menuItems" :key="item.path"
           class="nav-item" :class="{ active: currentPath === item.path }"
           @click="$router.push(item.path)">
        <el-icon :size="18"><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </div>
    </nav>

    <el-divider />

    <div class="section-title">已挂载资源</div>
    <div class="mount-list">
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
      <div v-if="mounts.mounts.length === 0" class="empty-hint">暂无挂载</div>
    </div>

    <div class="sidebar-bottom">
      <div class="webdav-toggle">
        <span>WebDAV 服务</span>
        <el-switch v-model="webdavRunning" size="small" />
      </div>
      <el-button type="primary" size="small" plain style="width:100%" @click="$router.push('/mounts')">
        <el-icon><Plus /></el-icon>快速连接
      </el-button>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { FolderOpened, Connection, User, Upload, Setting, Plus, Monitor, Cloudy, DataLine } from '@element-plus/icons-vue'
import { useMountsStore } from '@/stores/mounts'
import { useFilesStore } from '@/stores/files'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const mounts = useMountsStore()
const files = useFilesStore()
const auth = useAuthStore()
const webdavRunning = ref(false)
const currentPath = computed(() => route.path)

// 所有菜单项 (adminOnly 标记的仅管理员可见)
const allMenuItems = [
  { path: '/files', label: '文件浏览器', icon: FolderOpened },
  { path: '/mounts', label: '挂载管理', icon: Connection },
  { path: '/transfers', label: '传输任务', icon: Upload },
  { path: '/users', label: '用户与权限', icon: User, adminOnly: true },
  { path: '/settings', label: '系统设置', icon: Setting, adminOnly: true },
  { path: '/monitor', label: '请求监控', icon: DataLine, adminOnly: true },
]

// 根据管理员身份过滤菜单
const menuItems = computed(() =>
  auth.isAdmin ? allMenuItems : allMenuItems.filter((i) => !i.adminOnly)
)

const iconMap = { local: FolderOpened, ftp: Connection, sftp: Connection, webdav: Monitor, oss: Cloudy, s3: Cloudy }
function mountTypeIcon(type) { return iconMap[type] || Connection }

// 按类型分组挂载资源
const typeOrder = ['local', 'ftp', 'sftp', 'webdav', 'oss', 's3']
const typeLabels = { local: '本地存储', ftp: 'FTP', sftp: 'SFTP', webdav: 'WebDAV', oss: '阿里云 OSS', s3: 'Amazon S3' }
const groupedMounts = computed(() => {
  const map = {}
  for (const m of mounts.mounts) {
    if (!map[m.type]) map[m.type] = []
    map[m.type].push(m)
  }
  return typeOrder.filter((t) => map[t]).map((t) => ({ type: t, label: typeLabels[t] || t, items: map[t] }))
})

onMounted(() => { mounts.fetchMounts() })
</script>

<style scoped>
.side-panel {
  width: var(--sidebar-width);
  background: var(--card-bg);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  padding: 12px;
  overflow-y: auto;
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
</style>
