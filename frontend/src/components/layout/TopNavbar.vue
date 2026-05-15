<template>
  <header class="top-navbar">
    <div class="navbar-left">
      <el-icon :size="24" color="#409eff"><FolderOpened /></el-icon>
      <span class="logo-text">MultiMount</span>
      <span class="logo-subtitle">多协议文件挂载平台</span>
    </div>
    <div class="navbar-center">
      <el-input
        v-model="searchQuery"
        placeholder="搜索文件、挂载源..."
        :prefix-icon="Search"
        clearable
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
        <el-icon color="#67c23a" :size="18"><Lock /></el-icon>
      </el-tooltip>
      <el-badge :value="3" :max="99" class="notification-badge">
        <el-icon :size="18"><Bell /></el-icon>
      </el-badge>
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
import { FolderOpened, Search, Lock, Bell, Setting, SwitchButton, Sunny, Moon } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const searchQuery = ref('')
const isDark = ref(document.documentElement.classList.contains('dark'))

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
}

function handleLogout() {
  auth.logout()
  router.push('/login')
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
</style>
