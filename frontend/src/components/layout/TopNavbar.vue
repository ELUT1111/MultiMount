<template>
  <header class="top-navbar">
    <div class="navbar-left">
      <el-icon :size="24" class="logo-icon"><FolderOpened /></el-icon>
      <span class="logo-text">MultiMount</span>
      <span class="logo-subtitle">多协议文件挂载平台</span>
    </div>
    <div class="navbar-center">
      <el-input
        ref="searchInputRef"
        v-model="searchQuery"
        placeholder="搜索文件名..."
        :prefix-icon="Search"
        clearable
        @keyup.enter="handleSearch"
        style="max-width: 420px"
      />
      <el-tooltip :content="search.useRegex ? '正则匹配: 开' : '正则匹配: 关'" placement="bottom">
        <el-button
          :type="search.useRegex ? 'primary' : ''"
          :icon="Filter"
          size="default"
          @click="search.useRegex = !search.useRegex"
          style="flex-shrink: 0"
        >正则</el-button>
      </el-tooltip>
    </div>
    <div class="navbar-right">
      <el-button class="mobile-search-btn" :icon="Search" circle text @click="showMobileSearch = true" />
      <el-tooltip content="快捷键说明" placement="bottom">
        <el-button :icon="InfoFilled" circle text aria-label="快捷键说明" @click="showShortcutDialog = true" />
      </el-tooltip>
      <el-dropdown trigger="click" @command="handleThemeCommand">
        <el-button class="theme-button" :icon="appPrefs.isDark ? Moon : Sunny" circle text aria-label="主题设置" />
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="system">跟随系统</el-dropdown-item>
            <el-dropdown-item command="light">浅色主题</el-dropdown-item>
            <el-dropdown-item command="dark">深色主题</el-dropdown-item>
            <el-dropdown-item command="contrast" divided>
              {{ appPrefs.highContrast ? '关闭高对比' : '开启高对比' }}
            </el-dropdown-item>
            <el-dropdown-item command="compact">
              {{ appPrefs.compactMode ? '关闭紧凑模式' : '开启紧凑模式' }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-tooltip content="所有传输已通过 SSL/TLS 加密" placement="bottom">
        <el-icon class="lock-icon" :size="18"><Lock /></el-icon>
      </el-tooltip>

      <!-- 通知铃铛 + 弹出面板 -->
      <el-popover placement="bottom-end" :width="420" trigger="click" @show="onNotifShow">
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
          <div class="notif-filters">
            <el-button-group>
              <el-button size="small" :type="notifFilterActive('all') ? 'primary' : ''" @click="setNotifFilter('all')">全部</el-button>
              <el-button size="small" :type="notifFilterActive('unread') ? 'primary' : ''" @click="setNotifFilter('unread')">未读</el-button>
              <el-button size="small" :type="notifFilterActive('pending') ? 'primary' : ''" @click="setNotifFilter('pending')">待处理</el-button>
            </el-button-group>
            <el-select
              v-model="notif.filters.type"
              clearable
              size="small"
              placeholder="类型"
              class="notif-type-select"
              @change="refreshNotifications"
              @clear="refreshNotifications"
            >
              <el-option
                v-for="type in notif.typeOptions"
                :key="type"
                :label="notificationTypeLabel(type)"
                :value="type"
              />
            </el-select>
            <el-checkbox v-model="notif.filters.includeArchived" size="small" @change="refreshNotifications">含归档</el-checkbox>
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
                <div class="notif-item-head">
                  <div class="notif-item-title">{{ n.title }}</div>
                  <div class="notif-item-tools" @click.stop>
                    <el-button
                      v-if="!n.is_archived"
                      size="small"
                      text
                      @click="handleArchive(n)"
                    >归档</el-button>
                    <el-button
                      size="small"
                      text
                      type="danger"
                      @click="handleDelete(n)"
                    >删除</el-button>
                  </div>
                </div>
                <div class="notif-item-content">{{ n.content }}</div>
                <div class="notif-item-time">{{ formatNotifTime(n.created_at) }}</div>
                <!-- 可执行通知的操作按钮 -->
                <div v-if="isActionable(n)" class="notif-actions" @click.stop>
                  <template v-if="n.type === 'access_request'">
                    <el-button size="small" type="success" text :loading="actingIds.has(n.id)" @click="handleApprove(n)">同意</el-button>
                    <el-button size="small" type="danger" text :loading="actingIds.has(n.id)" @click="handleDeny(n)">拒绝</el-button>
                    <el-button size="small" type="primary" text @click="goToPermDialog(n)">查看</el-button>
                  </template>
                </div>
              </div>
            </div>
            <div v-if="notif.hasMore" class="notif-more">
              <el-button size="small" text :loading="notif.loadingMore" @click="notif.loadMoreNotifications()">加载更多</el-button>
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
            <el-dropdown-item :icon="Setting" @click="router.push('/profile')">个人设置</el-dropdown-item>
            <el-dropdown-item :icon="SwitchButton" divided @click="handleLogout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <el-dialog v-model="showMobileSearch" title="搜索文件" width="92%" class="mobile-search-dialog">
      <div class="mobile-search-box">
        <el-input
          v-model="searchQuery"
          placeholder="搜索文件名..."
          :prefix-icon="Search"
          clearable
          @keyup.enter="handleSearch"
        />
        <el-button :type="search.useRegex ? 'primary' : ''" @click="search.useRegex = !search.useRegex">正则</el-button>
        <el-button type="primary" @click="handleSearch">搜索</el-button>
      </div>
    </el-dialog>

    <el-dialog v-model="showShortcutDialog" title="快捷键说明" width="520px" class="responsive-dialog shortcut-dialog">
      <div class="shortcut-grid">
        <div v-for="item in shortcutItems" :key="item.keys" class="shortcut-row">
          <kbd>{{ item.keys }}</kbd>
          <span>{{ item.desc }}</span>
        </div>
      </div>
    </el-dialog>
  </header>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { FolderOpened, Search, Lock, Bell, Setting, SwitchButton, Sunny, Moon, Warning, CircleCheck, InfoFilled, Filter } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { useSearchStore } from '@/stores/search'
import { useAppStore } from '@/stores/app'
import { handleNotificationAction } from '@/api/notifications'

const router = useRouter()
const auth = useAuthStore()
const notif = useNotificationsStore()
const search = useSearchStore()
const appPrefs = useAppStore()
const searchQuery = ref('')
const searchInputRef = ref()
const showMobileSearch = ref(false)
const showShortcutDialog = ref(false)
const actingIds = ref(new Set())

const shortcutItems = [
  { keys: 'Ctrl / Cmd + K', desc: '聚焦全局搜索' },
  { keys: 'Ctrl / Cmd + A', desc: '在文件浏览器全选当前页' },
  { keys: 'Shift + ↑ / ↓', desc: '在文件浏览器范围选择' },
  { keys: 'Ctrl / Cmd + C / X / V', desc: '复制、剪切、粘贴文件' },
  { keys: 'Enter', desc: '打开目录或预览文件' },
  { keys: 'Delete', desc: '删除选中项' },
  { keys: 'Esc', desc: '清空选择或关闭当前弹窗' },
  { keys: '?', desc: '打开快捷键说明' },
]

function handleThemeCommand(command) {
  if (command === 'contrast') appPrefs.toggleHighContrast()
  else if (command === 'compact') appPrefs.toggleCompactMode()
  else appPrefs.setTheme(command)
}

function handleSearch() {
  const q = searchQuery.value.trim()
  if (!q) return
  search.query = q
  showMobileSearch.value = false
  router.push({ path: '/files', query: { q } })
}

function isTypingTarget(target) {
  const tag = target?.tagName?.toLowerCase()
  return tag === 'input' || tag === 'textarea' || tag === 'select' || target?.isContentEditable
}

function handleGlobalKeydown(event) {
  const lower = event.key.toLowerCase()
  if ((event.ctrlKey || event.metaKey) && lower === 'k') {
    event.preventDefault()
    searchInputRef.value?.focus?.()
    return
  }
  if (isTypingTarget(event.target)) return
  if (event.key === '?') {
    event.preventDefault()
    showShortcutDialog.value = true
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}

function onNotifShow() {
  notif.fetchNotifications()
}

function notifFilterActive(filter) {
  if (filter === 'unread') return notif.filters.unreadOnly && !notif.filters.pendingOnly
  if (filter === 'pending') return notif.filters.pendingOnly
  return !notif.filters.unreadOnly && !notif.filters.pendingOnly
}

function setNotifFilter(filter) {
  if (filter === 'unread') {
    notif.fetchNotifications({ unreadOnly: true, pendingOnly: false })
  } else if (filter === 'pending') {
    notif.fetchNotifications({ unreadOnly: false, pendingOnly: true })
  } else {
    notif.fetchNotifications({ unreadOnly: false, pendingOnly: false })
  }
}

function refreshNotifications() {
  notif.fetchNotifications({
    unreadOnly: notif.filters.unreadOnly,
    type: notif.filters.type,
    pendingOnly: notif.filters.pendingOnly,
    includeArchived: notif.filters.includeArchived,
  })
}

function notificationTypeLabel(type) {
  const labels = {
    access_request: '权限申请',
    permission_granted: '权限授予',
    permission_denied: '权限拒绝',
    permission_changed: '权限变更',
    mount_deleted: '挂载删除',
    mount_status: '挂载状态',
    account_disabled: '账号禁用',
  }
  return labels[type] || type
}

function notifIcon(type) {
  if (type === 'mount_deleted' || type === 'account_disabled') return Warning
  if (type === 'permission_changed' || type === 'access_request') return InfoFilled
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

function isActionable(n) {
  return n.type === 'access_request' && n.metadata?.requester_id && !n.metadata?.action_status
}

async function handleApprove(n) {
  actingIds.value.add(n.id)
  try {
    const data = await handleNotificationAction(n.id, 'approve')
    ElMessage.success('已同意权限申请')
    n.is_read = true
    n.metadata = { ...(n.metadata || {}), action_status: 'approved' }
    if (typeof data?.unread_count === 'number') notif.unreadCount = data.unread_count
  } catch {
    ElMessage.error('操作失败')
  } finally {
    actingIds.value.delete(n.id)
  }
}

async function handleDeny(n) {
  actingIds.value.add(n.id)
  try {
    const data = await handleNotificationAction(n.id, 'deny')
    ElMessage.success('已拒绝权限申请')
    n.is_read = true
    n.metadata = { ...(n.metadata || {}), action_status: 'denied' }
    if (typeof data?.unread_count === 'number') notif.unreadCount = data.unread_count
  } catch {
    ElMessage.error('操作失败')
  } finally {
    actingIds.value.delete(n.id)
  }
}

async function handleArchive(n) {
  try {
    await notif.archiveOne(n.id)
    ElMessage.success('已归档')
  } catch {
    ElMessage.error('归档失败')
  }
}

async function handleDelete(n) {
  try {
    await notif.deleteOne(n.id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

function goToPermDialog(n) {
  const mountId = n.related_id
  if (!n.is_read) notif.markNotificationRead(n.id)
  router.push({ path: '/mounts', query: { open_perms: mountId } })
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
  gap: 8px;
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
.theme-button {
  cursor: pointer;
  color: var(--text-regular);
  transition: color 0.2s;
}
.theme-button:hover { color: var(--primary-color); }
.mobile-search-btn { display: none; }
.mobile-search-box { display: flex; gap: 8px; }
.shortcut-grid { display: grid; gap: 8px; }
.shortcut-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color);
}
.shortcut-row kbd {
  flex: 0 0 auto;
  min-width: 132px;
  padding: 4px 8px;
  border: 1px solid var(--border-color);
  border-bottom-width: 2px;
  border-radius: 6px;
  background: var(--bg-color);
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
  text-align: center;
}

/* 通知面板 */
.notif-panel { max-height: 480px; display: flex; flex-direction: column; }
.notif-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.notif-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.notif-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.notif-type-select { width: 118px; }
.notif-empty { text-align: center; padding: 24px 0; color: var(--text-secondary); font-size: 13px; }
.notif-list { overflow-y: auto; max-height: 380px; display: flex; flex-direction: column; gap: 2px; }
.notif-item {
  display: flex; gap: 10px; padding: 10px 8px; border-radius: 6px; cursor: pointer;
  transition: background 0.15s;
}
.notif-item:hover { background: rgba(64,158,255,0.06); }
.notif-item.unread { background: rgba(64,158,255,0.04); }
.notif-item .el-icon { margin-top: 2px; flex-shrink: 0; }
.notif-icon-mount_deleted, .notif-icon-account_disabled { color: var(--danger-color); }
.notif-icon-permission_changed, .notif-icon-access_request { color: var(--warning-color); }
.notif-icon-mount_status { color: var(--info-color); }
.notif-body { flex: 1; min-width: 0; }
.notif-item-head { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 2px; }
.notif-item-title { flex: 1; min-width: 0; font-size: 13px; font-weight: 600; color: var(--text-primary); }
.notif-item-tools { display: none; flex: 0 0 auto; gap: 2px; }
.notif-item:hover .notif-item-tools { display: flex; }
.notif-item-content { font-size: 12px; color: var(--text-regular); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.notif-item-time { font-size: 11px; color: var(--text-secondary); margin-top: 4px; }
.notif-actions { display: flex; gap: 4px; margin-top: 6px; }
.notif-more { display: flex; justify-content: center; padding: 6px 0 2px; }

/* 响应式 */
@media (max-width: 768px) {
  .navbar-center { display: none; }
  .logo-subtitle { display: none; }
  .logo-text { font-size: 16px; }
  .navbar-left { min-width: auto; }
  .navbar-right { min-width: auto; gap: 12px; }
  .username { display: none; }
  .lock-icon { display: none; }
  .mobile-search-btn { display: inline-flex; }
  .top-navbar { padding: 0 12px; }
  .notification-badge :deep(.el-badge__content) { transform: translateY(-3px) translateX(8px); }
  .mobile-search-box { flex-direction: column; }
  .notif-type-select { width: 104px; }
}
</style>
