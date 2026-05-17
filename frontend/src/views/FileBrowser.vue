<!--
  文件浏览器主页面 — 核心功能页面。
  包含: 面包屑导航、列表/网格视图、拖拽上传、右键菜单、文件预览、详情面板。
-->
<template>
  <div class="file-browser" @dragover.prevent="onDragOver" @dragleave="onDragLeave" @drop.prevent="onDrop">
    <!-- 顶部工具栏 (搜索模式下隐藏) -->
    <div v-if="!search.searched" class="file-toolbar">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item v-for="(crumb, i) in breadcrumbs" :key="i">
          <a v-if="i < breadcrumbs.length - 1" @click="navigateTo(crumb.path)">{{ crumb.name }}</a>
          <span v-else>{{ crumb.name }}</span>
        </el-breadcrumb-item>
      </el-breadcrumb>
      <div class="toolbar-actions">
        <el-button-group>
          <el-button :type="files.viewMode === 'list' ? 'primary' : ''" @click="files.setViewMode('list')" :icon="List" />
          <el-button :type="files.viewMode === 'grid' ? 'primary' : ''" @click="files.setViewMode('grid')" :icon="Grid" />
        </el-button-group>
        <el-select v-model="files.sortBy" style="width: 120px" size="default">
          <el-option label="名称" value="name" />
          <el-option label="大小" value="size" />
          <el-option label="修改时间" value="modified" />
        </el-select>
        <el-button :icon="FolderAdd" @click="handleMkdir">新建文件夹</el-button>
        <el-upload :show-file-list="false" :before-upload="handleUpload" multiple>
          <el-button :icon="UploadFilled">上传文件</el-button>
        </el-upload>
        <el-button :icon="Finished" :type="batchMode ? 'primary' : ''" @click="toggleBatchMode">批量选择</el-button>
        <el-button v-if="batchMode && selectedFiles.length" type="danger" plain @click="handleBatchDelete">
          删除 ({{ selectedFiles.length }})
        </el-button>
        <el-button :icon="Refresh" @click="files.refresh()">刷新</el-button>
      </div>
    </div>

    <!-- 搜索模式工具栏 -->
    <div v-if="search.searched" class="search-toolbar">
      <div class="search-filters">
        <el-input v-model="search.query" placeholder="搜索关键词" size="default" style="width: 200px" @keyup.enter="doSearch" clearable />
        <el-tooltip :content="search.useRegex ? '正则匹配: 开' : '正则匹配: 关'">
          <el-button :type="search.useRegex ? 'primary' : ''" size="default" @click="search.useRegex = !search.useRegex">.*</el-button>
        </el-tooltip>
        <el-select v-model="search.filterByMount" placeholder="挂载源" clearable size="default" style="width: 140px">
          <el-option v-for="m in search.availableMounts" :key="m" :label="m" :value="m" />
        </el-select>
        <el-select v-model="search.filterByOwner" placeholder="创建者" clearable size="default" style="width: 120px">
          <el-option v-for="o in search.availableOwners" :key="o" :label="o" :value="o" />
        </el-select>
        <el-button type="primary" @click="doSearch" :loading="search.loading">搜索</el-button>
      </div>
      <div class="search-meta">
        <span>找到 {{ search.filteredResults.length }} 个结果</span>
        <el-button text type="primary" size="small" @click="exitSearch">返回浏览</el-button>
      </div>
    </div>

    <!-- 拖拽上传遮罩层 -->
    <div v-if="dragging" class="drag-overlay">
      <el-icon :size="48" color="var(--primary-color)"><UploadFilled /></el-icon>
      <p>拖拽文件至此上传</p>
    </div>

    <!-- 主内容区 -->
    <div class="file-content-wrapper">
      <div v-loading="files.loading || search.loading" class="file-content">
        <el-empty v-if="!search.searched && !files.loading && files.sortedFiles.length === 0" description="此目录为空" />
        <el-empty v-if="search.searched && !search.loading && search.filteredResults.length === 0" description="未找到匹配的文件" />
        <div v-if="!search.searched && files.totalPages > 1" class="file-pagination">
          <el-pagination
            v-model:current-page="files.page"
            :page-size="files.pageSize"
            :total="files.sortedFiles.length"
            layout="total, prev, pager, next"
            small
            @current-change="(p) => files.setPage(p)"
          />
        </div>

        <!-- 列表视图 -->
        <el-table
          v-if="files.viewMode === 'list' && (search.searched ? search.filteredResults.length : files.sortedFiles.length)"
          :data="search.searched ? search.filteredResults : files.pagedFiles"
          style="width: 100%"
          highlight-current-row
          @row-dblclick="handleDblClick"
          @row-contextmenu.prevent="onRowContextMenu"
          @row-click="files.selectFile"
          @selection-change="handleSelectionChange"
        >
          <!-- 批量选择列 -->
          <el-table-column v-if="batchMode" type="selection" width="40" />
          <el-table-column width="40">
            <template #default="{ row }">
              <el-icon v-if="row.is_dir" color="var(--primary-color)"><Folder /></el-icon>
              <el-icon v-else><Document /></el-icon>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" min-width="200" show-overflow-tooltip />
          <el-table-column label="大小" width="120">
            <template #default="{ row }">{{ row.is_dir ? '-' : formatSize(row.size) }}</template>
          </el-table-column>
          <el-table-column label="修改时间" width="180">
            <template #default="{ row }">{{ formatTime(row.modified_at) }}</template>
          </el-table-column>
          <el-table-column label="挂载源" width="120">
            <template #default="{ row }">{{ search.searched ? row.mount_name : currentMountName }}</template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click.stop="handleDownload(row)" v-if="!row.is_dir">下载</el-button>
              <el-button link type="primary" size="small" @click.stop="handlePreview(row)" v-if="canPreview(row)">预览</el-button>
              <el-button link type="primary" size="small" @click.stop="handleRename(row)">重命名</el-button>
              <el-button link type="primary" size="small" @click.stop="handleMove(row)">移动</el-button>
              <el-button link type="danger" size="small" @click.stop="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 网格视图 -->
        <div v-if="files.viewMode === 'grid' && (search.searched ? search.filteredResults.length : files.sortedFiles.length)" class="file-grid">
          <div v-for="file in (search.searched ? search.filteredResults : files.pagedFiles)" :key="file.path" class="file-card"
               :class="{ selected: files.selectedFile?.path === file.path || selectedFiles.some(f => f.path === file.path) }"
               @dblclick="handleDblClick(file)"
               @click="batchMode ? toggleFileSelection(file) : files.selectFile(file)"
               @contextmenu.prevent="onCardContextMenu($event, file)">
            <div v-if="batchMode" class="card-checkbox">
              <el-checkbox :model-value="selectedFiles.some(f => f.path === file.path)" @click.stop />
            </div>
            <div class="card-icon">
              <el-icon :size="40" v-if="file.is_dir" color="var(--primary-color)"><Folder /></el-icon>
              <el-icon :size="40" v-else><Document /></el-icon>
            </div>
            <div class="card-name" :title="file.name">{{ file.name }}</div>
            <div class="card-meta">
              <span v-if="!file.is_dir">{{ formatSize(file.size) }}</span>
              <span v-if="file.modified_at" class="card-time">{{ formatTime(file.modified_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧详情面板 -->
      <DetailPanel
        :file="files.selectedFile"
        @download="handleDownload"
        @rename="handleRename"
        @delete="handleDelete"
      />
    </div>

    <!-- 右键菜单 -->
    <FileContextMenu ref="contextMenuRef" :clipboard="clipboard" @action="handleContextAction" />

    <!-- 文件预览 -->
    <FilePreview v-model="showPreview" :mount-id="files.currentMountId" :file="previewFile" @download="handleDownload(previewFile)" />

    <!-- 上传进度 -->
    <div v-if="upload.uploading.value" class="upload-bar">
      <span>正在上传: {{ upload.currentFile.value }}</span>
      <el-progress :percentage="upload.progress.value" :stroke-width="6" style="flex: 1" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { List, Grid, FolderAdd, UploadFilled, Refresh, Folder, Document, Finished } from '@element-plus/icons-vue'
import { deleteFile, createDirectory, moveFile, downloadFile } from '@/api/files'
import { formatSize, formatTime } from '@/utils/format'
import { useFilesStore } from '@/stores/files'
import { useUpload } from '@/composables/useUpload'
import { useMountsStore } from '@/stores/mounts'
import { useSearchStore } from '@/stores/search'
import DetailPanel from '@/components/layout/DetailPanel.vue'
import FileContextMenu from '@/components/file/FileContextMenu.vue'
import FilePreview from '@/components/file/FilePreview.vue'

const route = useRoute()
const files = useFilesStore()
const mounts = useMountsStore()
const upload = useUpload()
const search = useSearchStore()

const contextMenuRef = ref()
const dragging = ref(false)
const showPreview = ref(false)
const previewFile = ref(null)
const clipboard = ref(null) // { action: 'copy'|'cut', file: FileInfo }
const batchMode = ref(false)
const selectedFiles = ref([])

// 当前挂载名称（用于列表视图的挂载源列）
const currentMountName = computed(() => {
  const m = mounts.mounts.find((m) => m.id === files.currentMountId)
  return m?.name || '-'
})

// 面包屑导航
const breadcrumbs = computed(() => {
  const parts = files.currentPath.split('/').filter(Boolean)
  const crumbs = [{ name: '根目录', path: '/' }]
  let path = ''
  for (const part of parts) {
    path += '/' + part
    crumbs.push({ name: part, path })
  }
  return crumbs
})

// 导航到指定路径
function navigateTo(path) {
  files.fetchFiles(files.currentMountId, path)
}

// 批量选择模式切换
function toggleBatchMode() {
  batchMode.value = !batchMode.value
  if (!batchMode.value) selectedFiles.value = []
}

// 表格 selection-change 回调
function handleSelectionChange(rows) {
  selectedFiles.value = rows
}

// 网格视图切换选中
function toggleFileSelection(file) {
  const idx = selectedFiles.value.findIndex((f) => f.path === file.path)
  if (idx >= 0) selectedFiles.value.splice(idx, 1)
  else selectedFiles.value.push(file)
}

// 批量删除 (并行执行)
async function handleBatchDelete() {
  await ElMessageBox.confirm(`确定删除选中的 ${selectedFiles.value.length} 个项目?`, '确认删除', { type: 'warning' })
  const results = await Promise.allSettled(
    selectedFiles.value.map((f) => deleteFile(files.currentMountId, f.path))
  )
  const failed = results.filter((r) => r.status === 'rejected').length
  if (failed === 0) {
    ElMessage.success(`已删除 ${selectedFiles.value.length} 个项目`)
  } else {
    ElMessage.warning(`删除完成，${failed} 个项目失败`)
  }
  selectedFiles.value = []
  batchMode.value = false
  files.refresh()
}

// 移动文件
async function handleMove(file) {
  const { value } = await ElMessageBox.prompt('请输入目标路径', '移动', {
    inputValue: file.path,
    inputValidator: (v) => !!v.trim() || '路径不能为空',
  })
  await moveFile(files.currentMountId, file.path, value.trim())
  ElMessage.success('已移动')
  files.refresh()
}

// 双击: 进入目录 (搜索模式下导航到对应挂载)
function handleDblClick(file) {
  if (file.is_dir) {
    if (search.searched) {
      exitSearch()
      files.fetchFiles(file.mount_id, file.path)
    } else {
      files.fetchFiles(files.currentMountId, file.path)
    }
  } else {
    handlePreview(file)
  }
}

// 判断是否可预览
function canPreview(file) {
  if (file.is_dir) return false
  const mime = file.mime_type || ''
  return mime.startsWith('image/') || mime.startsWith('text/') || ['application/json'].includes(mime)
}

// 预览
function handlePreview(file) {
  previewFile.value = file
  showPreview.value = true
}

// 下载
async function handleDownload(file) {
  if (!file || file.is_dir) return
  try {
    const blob = await downloadFile(files.currentMountId, file.path)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = file.name
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`下载: ${file.name}`)
  } catch {
    ElMessage.error('下载失败')
  }
}

// 删除
async function handleDelete(file) {
  await ElMessageBox.confirm(`确定删除 "${file.name}"?`, '确认删除', { type: 'warning' })
  await deleteFile(files.currentMountId, file.path)
  ElMessage.success('已删除')
  files.refresh()
}

// 重命名
async function handleRename(file) {
  const { value } = await ElMessageBox.prompt('请输入新名称', '重命名', {
    inputValue: file.name,
    inputValidator: (v) => !!v.trim() || '名称不能为空',
  })
  const parent = file.path.substring(0, file.path.lastIndexOf('/')) || '/'
  const newPath = parent + '/' + value.trim()
  await moveFile(files.currentMountId, file.path, newPath)
  ElMessage.success('已重命名')
  files.refresh()
}

// 新建目录
async function handleMkdir() {
  const { value } = await ElMessageBox.prompt('请输入文件夹名称', '新建文件夹', {
    inputValidator: (v) => !!v.trim() || '名称不能为空',
  })
  await createDirectory(files.currentMountId, files.currentPath + '/' + value.trim())
  ElMessage.success('已创建')
  files.refresh()
}

// 上传 (el-upload before-upload 钩子)
function handleUpload(file) {
  upload.upload(files.currentMountId, files.currentPath, file).then(() => files.refresh())
  return false // 阻止 el-upload 自动上传
}

// ── 拖拽上传 ──────────────────────────────────────────────
let dragCounter = 0
function onDragOver() { dragging.value = true }
function onDragLeave() {
  dragCounter--
  if (dragCounter <= 0) { dragging.value = false; dragCounter = 0 }
}
function onDrop(e) {
  dragging.value = false
  dragCounter = 0
  const droppedFiles = e.dataTransfer?.files
  if (droppedFiles?.length) {
    upload.uploadMultiple(files.currentMountId, files.currentPath, droppedFiles).then(() => files.refresh())
  }
}

// ── 右键菜单 ──────────────────────────────────────────────
function onRowContextMenu(row, column, event) {
  files.selectFile(row)
  contextMenuRef.value.open(event, row)
}
function onCardContextMenu(event, file) {
  files.selectFile(file)
  contextMenuRef.value.open(event, file)
}
async function handleContextAction({ action, file }) {
  if (action === 'download') handleDownload(file)
  else if (action === 'rename') handleRename(file)
  else if (action === 'delete') handleDelete(file)
  else if (action === 'copy') clipboard.value = { action: 'copy', file }
  else if (action === 'cut') clipboard.value = { action: 'cut', file }
  else if (action === 'paste' && clipboard.value) {
    const src = clipboard.value.file.path
    const dst = files.currentPath + '/' + clipboard.value.file.name
    if (clipboard.value.action === 'copy') {
      const { copyFile } = await import('@/api/files')
      await copyFile(files.currentMountId, src, dst)
    } else {
      await moveFile(files.currentMountId, src, dst)
    }
    clipboard.value = null
    ElMessage.success('已粘贴')
    files.refresh()
  } else if (action === 'share') {
    handleShare(file)
  } else if (action === 'info') {
    files.selectFile(file)
  }
}

// 生成分享链接
async function handleShare(file) {
  try {
    const { createShareLink } = await import('@/api/files')
    const res = await createShareLink(files.currentMountId, file.path)
    await navigator.clipboard.writeText(res.url)
    ElMessage.success('分享链接已复制到剪贴板')
  } catch {
    ElMessage.error('生成分享链接失败')
  }
}

// ── 搜索 ──────────────────────────────────────────────
function doSearch() {
  if (!search.query.trim()) return
  search.search()
}

function exitSearch() {
  search.clearSearch()
  router.replace({ path: '/files' })
}

// 路由 query.q 变化时自动触发搜索
watch(() => route.query.q, (q) => {
  if (q) {
    search.query = q
    nextTick(() => search.search())
  }
}, { immediate: true })

// 初始化: 默认加载第一个挂载点 (非搜索模式)
onMounted(async () => {
  await mounts.fetchMounts()
  if (!route.query.q && mounts.mounts.length > 0) {
    files.fetchFiles(mounts.mounts[0].id, '/')
  }
})
</script>

<style scoped>
.file-browser { display: flex; flex-direction: column; gap: 12px; height: 100%; position: relative; }
.file-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; background: var(--card-bg); border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.toolbar-actions { display: flex; align-items: center; gap: 8px; }
.file-content-wrapper { flex: 1; display: flex; gap: 12px; min-height: 0; }
.file-content {
  flex: 1; padding: 16px; background: var(--card-bg); border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06); overflow: auto;
}
.file-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; }
.file-card {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 16px 8px; border-radius: 8px; cursor: pointer; transition: all 0.2s;
  border: 2px solid transparent;
}
.file-card:hover { background: rgba(64,158,255,0.08); }
.file-card.selected { border-color: var(--primary-color); background: rgba(64,158,255,0.06); }
.card-name {
  font-size: 13px; text-align: center; width: 100%;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.card-meta { font-size: 11px; color: var(--text-secondary); display: flex; flex-direction: column; align-items: center; gap: 2px; }
.card-time { font-size: 10px; color: var(--text-secondary); opacity: 0.7; }
.card-checkbox { position: absolute; top: 6px; left: 6px; }
.file-card { position: relative; }

/* 拖拽上传遮罩 */
.drag-overlay {
  position: absolute; inset: 0; z-index: 100;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px;
  background: rgba(64,158,255,0.1); border: 3px dashed var(--primary-color); border-radius: 12px;
  pointer-events: none;
}
.drag-overlay p { font-size: 16px; color: var(--primary-color); font-weight: 600; }

/* 分页 */
.file-pagination {
  display: flex; justify-content: center; padding: 12px 0 4px;
}

/* 上传进度条 */
.upload-bar {
  position: fixed; bottom: 20px; right: 20px; left: 280px; z-index: 200;
  display: flex; align-items: center; gap: 12px; padding: 12px 16px;
  background: var(--card-bg); border-radius: 10px; box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  font-size: 13px;
}

/* 搜索工具栏 */
.search-toolbar {
  padding: 12px 16px; background: var(--card-bg); border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06); display: flex; flex-direction: column; gap: 8px;
}
.search-filters { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.search-meta { display: flex; align-items: center; justify-content: space-between; font-size: 13px; color: var(--text-secondary); }
</style>
