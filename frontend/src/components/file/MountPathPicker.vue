<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="640px"
    append-to-body
    class="responsive-dialog mount-path-picker"
    @update:model-value="emit('update:modelValue', $event)"
    @open="init"
  >
    <div class="mount-path-layout">
      <div class="mount-path-form">
        <el-form label-width="78px">
          <el-form-item v-if="allowMountSelect" label="目标挂载">
            <el-select
              v-model="selectedMountId"
              class="mount-select"
              filterable
              placeholder="选择挂载点"
              @change="handleMountChange"
            >
              <el-option
                v-for="mount in mounts"
                :key="mount.id"
                :label="mount.name"
                :value="mount.id"
              >
                <span class="mount-option-name">{{ mount.name }}</span>
                <span class="mount-option-meta">#{{ mount.id }}</span>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="目标路径">
            <el-input
              v-model="manualPath"
              placeholder="输入挂载点内目录路径，如 /docs"
              clearable
              @keyup.enter="goManualPath"
            >
              <template #append>
                <el-button :icon="Position" :loading="loading" @click="goManualPath">前往</el-button>
              </template>
            </el-input>
          </el-form-item>
        </el-form>
      </div>

      <div class="picker-shell">
        <div class="picker-nav">
          <el-button :icon="Back" size="small" :disabled="currentPath === '/'" @click="goUp">上一级</el-button>
          <el-breadcrumb separator="/" class="picker-breadcrumb">
            <el-breadcrumb-item v-for="crumb in breadcrumbs" :key="crumb.path">
              <button class="crumb-button" type="button" @click="openPath(crumb.path)">
                {{ crumb.name }}
              </button>
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div v-loading="loading" class="directory-list">
          <button
            class="directory-item current"
            type="button"
            :class="{ selected: selectedPath === currentPath }"
            @click="selectPath(currentPath)"
            @dblclick="confirm"
          >
            <el-icon><FolderChecked /></el-icon>
            <span>选择当前目录</span>
            <small>{{ currentPath }}</small>
          </button>
          <el-empty v-if="!loading && directories.length === 0" description="当前目录没有子文件夹" :image-size="72" />
          <button
            v-for="dir in directories"
            :key="dir.path"
            class="directory-item"
            type="button"
            :class="{ selected: selectedPath === dir.path }"
            @click="selectPath(dir.path)"
            @dblclick="openPath(dir.path)"
          >
            <el-icon><FolderOpened /></el-icon>
            <span>{{ dir.name }}</span>
            <small>{{ dir.path }}</small>
          </button>
        </div>
      </div>

      <div class="selected-preview">
        <span>已选目录</span>
        <strong>{{ selectedPath || currentPath || '/' }}</strong>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :disabled="!selectedMountId || !normalizedSelectedPath" @click="confirm">
        {{ confirmText }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Back, FolderChecked, FolderOpened, Position } from '@element-plus/icons-vue'
import { listFiles } from '@/api/files'

const props = defineProps({
  modelValue: Boolean,
  title: { type: String, default: '选择目标目录' },
  confirmText: { type: String, default: '确认选择' },
  mounts: { type: Array, default: () => [] },
  mountId: { type: Number, default: null },
  path: { type: String, default: '/' },
  allowMountSelect: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const selectedMountId = ref(null)
const currentPath = ref('/')
const selectedPath = ref('/')
const manualPath = ref('/')
const directories = ref([])
const loading = ref(false)

const normalizedSelectedPath = computed(() => normalizePath(selectedPath.value || currentPath.value || '/'))
const breadcrumbs = computed(() => {
  const crumbs = [{ name: '根目录', path: '/' }]
  let path = ''
  for (const part of normalizedPath(currentPath.value).split('/').filter(Boolean)) {
    path += `/${part}`
    crumbs.push({ name: part, path })
  }
  return crumbs
})

watch(() => props.modelValue, (open) => {
  if (open) init()
})

function normalizePath(path) {
  const value = String(path || '/').replace(/\\/g, '/').replace(/\/+/g, '/').trim()
  if (!value || value === '.') return '/'
  return value.startsWith('/') ? value.replace(/\/+$/, '') || '/' : `/${value.replace(/\/+$/, '')}`
}

function init() {
  const fallbackMount = props.mounts[0]?.id || props.mountId
  selectedMountId.value = props.mountId || fallbackMount || null
  const initialPath = normalizePath(props.path || '/')
  currentPath.value = initialPath
  selectedPath.value = initialPath
  manualPath.value = initialPath
  if (selectedMountId.value) {
    loadDirectories(initialPath)
  } else {
    directories.value = []
  }
}

async function loadDirectories(path) {
  if (!selectedMountId.value) return
  const nextPath = normalizePath(path)
  loading.value = true
  try {
    const entries = await listFiles(selectedMountId.value, nextPath)
    directories.value = entries.filter((item) => item.is_dir)
    currentPath.value = nextPath
    selectedPath.value = nextPath
    manualPath.value = nextPath
  } catch (error) {
    directories.value = []
    ElMessage.error(error.response?.data?.detail || '目录加载失败')
  } finally {
    loading.value = false
  }
}

function handleMountChange() {
  loadDirectories('/')
}

function openPath(path) {
  loadDirectories(path)
}

function selectPath(path) {
  selectedPath.value = normalizePath(path)
  manualPath.value = selectedPath.value
}

function goManualPath() {
  const path = normalizePath(manualPath.value)
  loadDirectories(path)
}

function goUp() {
  const parts = normalizePath(currentPath.value).split('/').filter(Boolean)
  parts.pop()
  loadDirectories(parts.length ? `/${parts.join('/')}` : '/')
}

function confirm() {
  emit('confirm', {
    mountId: selectedMountId.value,
    path: normalizedSelectedPath.value,
    mount: props.mounts.find((mount) => mount.id === selectedMountId.value) || null,
  })
  emit('update:modelValue', false)
}
</script>

<style scoped>
.mount-path-layout {
  display: grid;
  gap: 12px;
}
.mount-select {
  width: 100%;
}
.mount-option-name {
  font-weight: 600;
}
.mount-option-meta {
  float: right;
  color: var(--text-secondary);
  font-size: 12px;
}
.picker-shell {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--card-bg);
  overflow: hidden;
}
.picker-nav {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
  background: color-mix(in srgb, var(--bg-color) 72%, var(--card-bg));
}
.picker-breadcrumb {
  min-width: 0;
}
.crumb-button {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--primary-color);
  font: inherit;
  cursor: pointer;
}
.directory-list {
  height: 330px;
  overflow: auto;
  padding: 8px;
}
.directory-item {
  width: 100%;
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 2px 8px;
  align-items: center;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
}
.directory-item:hover {
  background: rgba(64, 158, 255, 0.08);
}
.directory-item.selected {
  border-color: rgba(64, 158, 255, 0.36);
  background: rgba(64, 158, 255, 0.12);
}
.directory-item.current {
  margin-bottom: 6px;
  background: color-mix(in srgb, var(--primary-color) 8%, transparent);
}
.directory-item span {
  min-width: 0;
  overflow: hidden;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.directory-item small {
  grid-column: 2;
  min-width: 0;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.selected-preview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-color);
  font-size: 13px;
}
.selected-preview span {
  flex: 0 0 auto;
  color: var(--text-secondary);
}
.selected-preview strong {
  min-width: 0;
  overflow: hidden;
  color: var(--text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 768px) {
  .picker-nav,
  .selected-preview {
    align-items: stretch;
    flex-direction: column;
  }
  .directory-list {
    height: 280px;
  }
}
</style>
