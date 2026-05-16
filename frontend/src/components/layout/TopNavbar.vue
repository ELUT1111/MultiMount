<template>
  <header class="top-navbar">
    <div class="navbar-left">
      <el-icon :size="24" class="logo-icon"><FolderOpened /></el-icon>
      <span class="logo-text">MultiMount</span>
      <span class="logo-subtitle">多协议文件挂载平台</span>
    </div>
    <div class="navbar-center">
      <el-input
        v-model="searchQuery"
        placeholder="搜索文件、挂载源..."
        :prefix-icon="Search"
        clearable
        @keyup.enter="handleSearch"
        style="max-width: 480px"
      />
    </div>
    <div class="navbar-right">
      <!-- 深色/浅色主题切换 -->
      <el-tooltip :content="isDark ? '切换到浅色模式' : '切换到深色模式'" placement="bottom">
        <el-icon :size="18" class="theme-toggle" @click="toggleTheme">
          <component :is="isDark ? Sunny : Moon" />
        </el-icon>
      </el-tooltip>
      <el-tooltip content="所有传输已通过 SSL/TLS 加密" placement="bottom">
        <el-icon class="lock-icon" :size="18"><Lock /></el-icon>
      </el-tooltip>

      <!-- 通知铃铛 + 弹出面板 -->
      <el-popover placement="bottom-end" :width="360" trigger="click" @show="onNotifShow">
        <template #reference>
          <el-badge :value="notif.unreadCount" :hidden="!notif.unreadCount" :max="99" class="notification-badge">
            <el-icon :size="18"><Bell /></el-icon>
          </el-badge>
        </template>
        <div class="notif-panel">
          <div class="notif-header">
            <span class="notif-title">通知</span>
            <el-button v-if="notif.unreadCount" link type="primary" size="small" @click="notif.markAllNotificationsRead()">全部已读</el-button>
          </div>
          <div v-if="notif.loading" class="notif-empty">加载中...</div>
          <div v-else-if="notif.notifications.length === 0" class="notif-empty">暂无通知</div>
          <div v-else class="notif-list">
            <div
              v-for="n in notif.notifications"
              :key="n.id"
              class="notif-item"
              :class="{ unread: !n.is_read }"
              @click="handleNotifClick(n)"
            >
              <el-icon :size="16" :class="'notif-icon-' + n.type">
                <component :is="notifIcon(n.type)" />
              </el-icon>
              <div class="notif-body">
                <div class="notif-item-title">{{ n.title }}</div>
                <div class="notif-item-content">{{ n.content }}</div>
                <div class="notif-item-time">{{ formatNotifTime(n.created_at) }}</div>
              </div>
            </div>
          </div>
        </div>
      </el-popover>

      <el-dropdown trigger="click">
        <div class="user-info">
          <el-avatar :size="32">{{ auth.username?.[0]?.toUpperCase() || 'U' }}</el-avatar>
          <span class="username">{{ auth.username }}</span>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item :icon="Setting">个人设置</el-dropdown-item>
            <el-dropdown-item :icon="SwitchButton" divided @click="handleLogout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { FolderOpened, Search, Lock, Bell, Setting, SwitchButton, Sunny, Moon, Warning, CircleCheck, InfoFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'

const router = useRouter()
const auth = useAuthStore()
const notif = useNotificationsStore()
const searchQuery = ref('')
const isDark = ref(document.documentElement.classList.contains('dark'))

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
}

function handleSearch() {
  // 搜索功能暂未实现
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

function onNotifShow() {
  notif.fetchNotifications()
}

function notifIcon(type) {
  if (type === 'mount_deleted' || type === 'account_disabled') return Warning
  if (type === 'permission_changed') return InfoFilled
  return CircleCheck
}

function formatNotifTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return d.toLocaleString('zh-CN')
}

function handleNotifClick(n) {
  if (!n.is_read) notif.markNotificationRead(n.id)
}
</script>

<style scoped>
.top-navbar {
  height: var(--topbar-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--border-color);
}
.navbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 200px;
}
.logo-icon { color: var(--primary-color); }
.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}
.logo-subtitle {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.navbar-center {
  flex: 1;
  display: flex;
  justify-content: center;
}
.navbar-right {
  display: flex;
  align-items: center;
  gap: 20px;
  min-width: 200px;
  justify-content: flex-end;
}
.lock-icon { color: var(--success-color); }
.notification-badge {
  cursor: pointer;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}
.username {
  font-size: 14px;
  color: var(--text-regular);
}
.theme-toggle {
  cursor: pointer;
  color: var(--text-regular);
  transition: color 0.2s;
}
.theme-toggle:hover { color: var(--primary-color); }

/* 通知面板 */
.notif-panel { max-height: 400px; display: flex; flex-direction: column; }
.notif-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.notif-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.notif-empty { text-align: center; padding: 24px 0; color: var(--text-secondary); font-size: 13px; }
.notif-list { overflow-y: auto; max-height: 340px; display: flex; flex-direction: column; gap: 2px; }
.notif-item {
  display: flex; gap: 10px; padding: 10px 8px; border-radius: 6px; cursor: pointer;
  transition: background 0.15s;
}
.notif-item:hover { background: rgba(64,158,255,0.06); }
.notif-item.unread { background: rgba(64,158,255,0.04); }
.notif-item .el-icon { margin-top: 2px; flex-shrink: 0; }
.notif-icon-mount_deleted, .notif-icon-account_disabled { color: var(--danger-color); }
.notif-icon-permission_changed { color: var(--warning-color); }
.notif-icon-mount_status { color: var(--info-color); }
.notif-body { flex: 1; min-width: 0; }
.notif-item-title { font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 2px; }
.notif-item-content { font-size: 12px; color: var(--text-regular); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.notif-item-time { font-size: 11px; color: var(--text-secondary); margin-top: 4px; }

/* 响应式 */
@media (max-width: 768px) {
  .navbar-center { display: none; }
  .logo-subtitle { display: none; }
  .navbar-left { min-width: auto; }
  .navbar-right { min-width: auto; gap: 12px; }
}
</style>
