<!--
  文件右键菜单 — 在文件/目录上右键弹出, 提供复制/剪切/重命名/删除/下载等操作。
-->
<template>
  <teleport to="body">
    <transition name="fade">
      <div v-if="visible" class="context-menu-mask" @click="close" @contextmenu.prevent="close">
        <div class="context-menu" :style="menuStyle" @click.stop>
          <div v-if="file && !file.is_dir" class="menu-item" @click="handleAction('download')">
            <el-icon><Download /></el-icon><span>下载</span>
          </div>
          <div v-if="file && !file.is_dir" class="menu-item" @click="handleAction('share')">
            <el-icon><Share /></el-icon><span>生成分享链接</span>
          </div>
          <div class="menu-item" @click="handleAction('rename')">
            <el-icon><Edit /></el-icon><span>重命名</span>
          </div>
          <div class="menu-item" @click="handleAction('copy')">
            <el-icon><CopyDocument /></el-icon><span>复制</span>
          </div>
          <div class="menu-item" @click="handleAction('cut')">
            <el-icon><Scissor /></el-icon><span>剪切</span>
          </div>
          <div v-if="clipboard" class="menu-item" @click="handleAction('paste')">
            <el-icon><DocumentCopy /></el-icon><span>粘贴</span>
          </div>
          <div class="menu-item" @click="handleAction('info')">
            <el-icon><InfoFilled /></el-icon><span>属性</span>
          </div>
          <el-divider style="margin: 4px 0" />
          <div class="menu-item danger" @click="handleAction('delete')">
            <el-icon><Delete /></el-icon><span>删除</span>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Download, Edit, CopyDocument, Scissor, DocumentCopy, InfoFilled, Delete, Share } from '@element-plus/icons-vue'

const props = defineProps({
  clipboard: { type: Object, default: null },
})

const emit = defineEmits(['action'])

const visible = ref(false)
const file = ref(null)
const position = ref({ x: 0, y: 0 })

const menuStyle = computed(() => ({
  left: position.value.x + 'px',
  top: position.value.y + 'px',
}))

/** 打开菜单 (由父组件在 contextmenu 事件中调用) */
function open(event, targetFile) {
  file.value = targetFile
  position.value = { x: event.clientX, y: event.clientY }
  visible.value = true
}

function close() {
  visible.value = false
}

function handleAction(action) {
  emit('action', { action, file: file.value })
  close()
}

defineExpose({ open, close })
</script>

<style scoped>
.context-menu-mask {
  position: fixed; inset: 0; z-index: 9999;
}
.context-menu {
  position: fixed; background: var(--card-bg); border: 1px solid var(--border-color);
  border-radius: 8px; padding: 4px 0; min-width: 160px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12); z-index: 10000;
}
.menu-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 16px; cursor: pointer; font-size: 13px; color: var(--text-regular);
  transition: background 0.15s;
}
.menu-item:hover { background: rgba(64, 158, 255, 0.08); color: var(--primary-color); }
.menu-item.danger:hover { background: rgba(245, 108, 108, 0.08); color: var(--danger-color); }
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
