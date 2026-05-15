<template>
  <el-dialog :model-value="modelValue" title="选择文件夹" width="560px" @update:model-value="$emit('update:modelValue', $event)" @open="init">
    <!-- 当前路径 -->
    <div class="path-bar">
      <el-icon class="nav-btn" @click="goUp" :disabled="!currentPath"><Top /></el-icon>
      <el-input v-model="manualPath" size="small" placeholder="输入路径后回车" @keyup.enter="navigateTo(manualPath)" style="flex:1" />
      <el-button size="small" @click="navigateTo(manualPath)" :loading="loading">前往</el-button>
    </div>

    <!-- 目录列表 -->
    <div class="folder-list" v-loading="loading">
      <el-empty v-if="!loading && folders.length === 0" description="此目录下没有文件夹" :image-size="60" />
      <div v-for="f in folders" :key="f.path" class="folder-item" @dblclick="enterFolder(f)" @click="selectedPath = f.path">
        <el-icon :size="18" color="#409eff"><FolderOpened /></el-icon>
        <span class="folder-name">{{ f.name }}</span>
      </div>
    </div>

    <!-- 选中路径 -->
    <div class="selected-bar">
      <span class="label">选中路径:</span>
      <el-input v-model="selectedPath" size="small" readonly />
    </div>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="confirm" :disabled="!selectedPath">确认选择</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { FolderOpened, Top } from '@element-plus/icons-vue'
import { browseFolders } from '@/api/system'
import { ElMessage } from 'element-plus'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'select'])

const currentPath = ref('')
const manualPath = ref('')
const selectedPath = ref('')
const folders = ref([])
const loading = ref(false)

async function loadFolders(path) {
  loading.value = true
  try {
    folders.value = await browseFolders(path)
    currentPath.value = path
    manualPath.value = path
  } catch {
    folders.value = []
  } finally {
    loading.value = false
  }
}

function init() {
  currentPath.value = ''
  selectedPath.value = ''
  manualPath.value = ''
  loadFolders('')
}

function navigateTo(path) {
  if (!path) return init()
  loadFolders(path)
  selectedPath.value = path
}

function enterFolder(f) {
  loadFolders(f.path)
  selectedPath.value = f.path
}

function goUp() {
  if (!currentPath.value) return
  // 取父目录
  const sep = currentPath.value.includes('\\') ? '\\' : '/'
  const parts = currentPath.value.replace(/[\\/]+$/, '').split(sep)
  parts.pop()
  const parent = parts.length <= 1 && currentPath.value.includes('\\')
    ? parts[0] + sep
    : parts.join(sep) || ''
  navigateTo(parent)
}

function confirm() {
  if (!selectedPath.value) return
  emit('select', selectedPath.value)
  emit('update:modelValue', false)
}
</script>

<style scoped>
.path-bar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.nav-btn { cursor: pointer; font-size: 18px; color: var(--primary-color); flex-shrink: 0; }
.nav-btn[disabled] { opacity: 0.3; cursor: not-allowed; }
.folder-list { height: 320px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 6px; padding: 4px 0; }
.folder-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px; cursor: pointer;
  border-radius: 4px; transition: background 0.15s;
}
.folder-item:hover { background: rgba(64,158,255,0.08); }
.folder-name { font-size: 13px; }
.selected-bar { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
.selected-bar .label { font-size: 13px; color: var(--text-secondary); white-space: nowrap; }
</style>
