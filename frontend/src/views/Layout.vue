<!--
  主布局壳 — 顶部导航栏 + 左侧侧边栏 + 中间主内容区 (router-view)。
-->
<template>
  <div class="layout">
    <TopNavbar />
    <div
      class="layout-body"
      :class="{ 'sidebar-collapsed': sidebarCollapsed, 'sidebar-resizing': resizing }"
      :style="{ '--sidebar-width': `${sidebarWidth}px` }"
    >
      <div class="sidebar-frame">
        <SidePanel :collapsed="sidebarCollapsed" :compact="sidebarCompact" />
        <button
          class="sidebar-resizer"
          type="button"
          :aria-label="sidebarCollapsed ? '展开侧边栏' : '拖拽调整侧边栏宽度'"
          :title="sidebarCollapsed ? '点击展开侧边栏' : '拖拽调整宽度，双击收起'"
          @pointerdown="startResize"
          @dblclick="collapseSidebar"
        >
          <span class="resizer-grip" />
        </button>
      </div>
      <main class="layout-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import TopNavbar from '@/components/layout/TopNavbar.vue'
import SidePanel from '@/components/layout/SidePanel.vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useNotificationsStore } from '@/stores/notifications'

const notifications = useNotificationsStore()
const SIDEBAR_DEFAULT = 240
const SIDEBAR_MIN = 72
const SIDEBAR_MAX = 360
const SIDEBAR_COLLAPSE_AT = 36

const savedWidth = Number(localStorage.getItem('sidebarWidth'))
const sidebarWidth = ref(Number.isFinite(savedWidth) && savedWidth >= 0 ? savedWidth : SIDEBAR_DEFAULT)
const resizing = ref(false)
const sidebarCollapsed = computed(() => sidebarWidth.value === 0)
const sidebarCompact = computed(() => !sidebarCollapsed.value && sidebarWidth.value < 150)
let resizeStartX = 0
let resizeStartWidth = SIDEBAR_DEFAULT

// 全局通知 WebSocket
const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
const { data: wsData, connect: wsConnect } = useWebSocket(
  `${wsProtocol}//${location.host}/api/v1/notifications/ws`
)

watch(wsData, (val) => {
  if (val?.type?.startsWith('notification')) {
    notifications.handleWsMessage(val)
  }
})

onMounted(() => {
  wsConnect()
  notifications.fetchUnreadCount()
})

onBeforeUnmount(() => {
  stopResize()
})

function startResize(event) {
  if (window.matchMedia('(max-width: 768px)').matches) return
  if (sidebarCollapsed.value) {
    expandSidebar()
    return
  }
  resizing.value = true
  resizeStartX = event.clientX
  resizeStartWidth = sidebarWidth.value
  event.currentTarget.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', resizeSidebar)
  window.addEventListener('pointerup', stopResize)
}

function resizeSidebar(event) {
  if (!resizing.value) return
  const nextWidth = resizeStartWidth + event.clientX - resizeStartX
  if (nextWidth <= SIDEBAR_COLLAPSE_AT) {
    sidebarWidth.value = 0
    return
  }
  sidebarWidth.value = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, nextWidth))
}

function stopResize() {
  if (resizing.value) {
    localStorage.setItem('sidebarWidth', String(Math.round(sidebarWidth.value)))
  }
  resizing.value = false
  window.removeEventListener('pointermove', resizeSidebar)
  window.removeEventListener('pointerup', stopResize)
}

function collapseSidebar() {
  sidebarWidth.value = 0
  localStorage.setItem('sidebarWidth', '0')
}

function expandSidebar() {
  sidebarWidth.value = SIDEBAR_DEFAULT
  localStorage.setItem('sidebarWidth', String(SIDEBAR_DEFAULT))
}
</script>

<style scoped>
.layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.layout-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-width: 0;
}
.sidebar-frame {
  position: relative;
  flex: 0 0 var(--sidebar-width);
  width: var(--sidebar-width);
  min-width: 0;
  transition: flex-basis 0.18s ease, width 0.18s ease;
}
.sidebar-resizing .sidebar-frame {
  transition: none;
}
.sidebar-resizing {
  cursor: col-resize;
  user-select: none;
}
.sidebar-resizer {
  position: absolute;
  top: 0;
  right: -5px;
  z-index: 20;
  width: 10px;
  height: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: col-resize;
  touch-action: none;
}
.resizer-grip {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 4px;
  width: 2px;
  background: transparent;
  transition: background 0.15s, box-shadow 0.15s;
}
.sidebar-resizer:hover .resizer-grip,
.sidebar-resizer:focus-visible .resizer-grip,
.sidebar-resizing .resizer-grip {
  background: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.14);
}
.sidebar-collapsed .sidebar-resizer {
  right: -7px;
  width: 14px;
}
.sidebar-collapsed .resizer-grip {
  left: 6px;
  background: var(--border-color);
}
.layout-main {
  flex: 1;
  min-width: 0;
  padding: 16px;
  overflow: auto;
  background: var(--bg-color);
}

@media (max-width: 768px) {
  .layout-body {
    --sidebar-width: 0px !important;
  }
  .sidebar-frame {
    position: static;
    flex: 0 0 0;
    width: 0;
  }
  .sidebar-resizer {
    display: none;
  }
  .layout-main {
    padding: 12px;
    padding-bottom: 72px;
  }
}
</style>
