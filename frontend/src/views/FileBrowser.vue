<!--
  文件浏览器主页面 — 核心功能页面。
  包含: 面包屑导航、列表/网格视图、拖拽上传、右键菜单、文件预览、详情面板。
-->
<template>
  <div class="file-browser" @dragenter.prevent="onDragEnter" @dragover.prevent="onDragOver" @dragleave="onDragLeave" @drop.prevent="onDrop">
    <!-- 顶部工具栏 (搜索模式下隐藏) -->
    <div v-if="!search.searched" class="file-toolbar">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item v-for="(crumb, i) in breadcrumbs" :key="i">
          <a v-if="i < breadcrumbs.length - 1" @click="navigateTo(crumb.path)">{{ crumb.name }}</a>
          <span v-else>{{ crumb.name }}</span>
        </el-breadcrumb-item>
      </el-breadcrumb>
      <div class="toolbar-actions">
        <el-button :icon="FolderAdd" @click="handleMkdir" :disabled="!canWriteCurrentMount">新建文件夹</el-button>
        <el-upload :show-file-list="false" :before-upload="handleUpload" multiple :disabled="!canWriteCurrentMount">
          <el-button type="primary" :icon="UploadFilled" :disabled="!canWriteCurrentMount">上传文件</el-button>
        </el-upload>
        <el-dropdown trigger="click">
          <el-button :icon="MoreFilled">更多</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="files.setViewMode('list')">列表视图</el-dropdown-item>
              <el-dropdown-item @click="files.setViewMode('grid')">网格视图</el-dropdown-item>
              <el-dropdown-item divided @click="files.setSortBy('name')">按名称排序</el-dropdown-item>
              <el-dropdown-item @click="files.setSortBy('size')">按大小排序</el-dropdown-item>
              <el-dropdown-item @click="files.setSortBy('modified')">按修改时间排序</el-dropdown-item>
              <el-dropdown-item divided @click="toggleBatchMode">批量选择</el-dropdown-item>
              <el-dropdown-item @click="files.refresh()">刷新</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <div v-if="selectionActive" class="batch-toolbar">
      <span>已选择 {{ selectedFiles.length }} 个项目</span>
      <div class="batch-actions">
        <el-button size="small" @click="clearSelection" :disabled="!selectedFiles.length">清空选择</el-button>
        <el-button size="small" type="danger" plain @click="handleBatchDelete" :disabled="!selectedFiles.length">
          删除
        </el-button>
        <el-button v-if="batchMode" size="small" @click="toggleBatchMode">退出批量</el-button>
      </div>
    </div>

    <!-- 搜索模式工具栏 -->
    <div v-if="search.searched" class="search-toolbar">
      <div class="search-filters responsive-filters">
        <el-input v-model="search.query" placeholder="搜索关键词" size="default" @keyup.enter="doSearch" clearable />
        <el-tooltip :content="search.useRegex ? '正则匹配: 开' : '正则匹配: 关'">
          <el-button :type="search.useRegex ? 'primary' : ''" size="default" @click="search.useRegex = !search.useRegex">.*</el-button>
        </el-tooltip>
        <el-select v-model="search.filterByMount" placeholder="挂载源" clearable size="default">
          <el-option v-for="m in search.availableMounts" :key="m" :label="m" :value="m" />
        </el-select>
        <el-select v-model="search.filterByOwner" placeholder="创建者" clearable size="default">
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
      <p>{{ canWriteCurrentMount ? '拖拽文件至此上传' : '当前挂载不可上传' }}</p>
    </div>

    <!-- 主内容区 -->
    <div class="file-content-wrapper">
      <div v-loading="files.loading || search.loading" class="file-content">
        <el-empty v-if="!search.searched && !files.loading && emptyState" :description="emptyState.description">
          <el-button v-if="emptyState.action" type="primary" @click="emptyState.action">{{ emptyState.actionText }}</el-button>
        </el-empty>
        <el-empty
          v-if="search.searched && !search.loading && sortedSearchResults.length === 0"
          :description="search.error || '未找到匹配的文件'"
        />
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
          v-if="files.viewMode === 'list' && displayFiles.length"
          ref="fileTableRef"
          :data="displayFiles"
          :row-key="fileKey"
          :row-class-name="tableRowClassName"
          style="width: 100%"
          highlight-current-row
          @row-dblclick="handleDblClick"
          @row-contextmenu.prevent="onRowContextMenu"
          @row-click="handleFileClick"
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
          <el-table-column prop="name" min-width="200" show-overflow-tooltip>
            <template #header>
              <button class="sort-header" @click="handleSortHeaderClick('name')" @contextmenu.prevent="handleSortHeaderContextMenu('name')" :title="sortHeaderTitle('name')">
                <span>名称</span>
                <span v-if="sortRuleFor('name')" class="sort-state">
                  {{ sortRuleFor('name').order }} {{ sortRuleFor('name').direction === 'asc' ? 'ASC' : 'DESC' }}
                </span>
              </button>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="120" class-name="hide-sm" label-class-name="hide-sm">
            <template #header>
              <button class="sort-header" @click="handleSortHeaderClick('size')" @contextmenu.prevent="handleSortHeaderContextMenu('size')" :title="sortHeaderTitle('size')">
                <span>大小</span>
                <span v-if="sortRuleFor('size')" class="sort-state">
                  {{ sortRuleFor('size').order }} {{ sortRuleFor('size').direction === 'asc' ? 'ASC' : 'DESC' }}
                </span>
              </button>
            </template>
            <template #default="{ row }">{{ row.is_dir ? '-' : formatSize(row.size) }}</template>
          </el-table-column>
          <el-table-column label="修改时间" width="180">
            <template #header>
              <button class="sort-header" @click="handleSortHeaderClick('modified_at')" @contextmenu.prevent="handleSortHeaderContextMenu('modified_at')" :title="sortHeaderTitle('modified_at')">
                <span>修改时间</span>
                <span v-if="sortRuleFor('modified_at')" class="sort-state">
                  {{ sortRuleFor('modified_at').order }} {{ sortRuleFor('modified_at').direction === 'asc' ? 'ASC' : 'DESC' }}
                </span>
              </button>
            </template>
            <template #default="{ row }">{{ formatTime(row.modified_at) }}</template>
          </el-table-column>
          <el-table-column label="创建时间" width="180" class-name="hide-sm" label-class-name="hide-sm">
            <template #header>
              <button class="sort-header" @click="handleSortHeaderClick('created_at')" @contextmenu.prevent="handleSortHeaderContextMenu('created_at')" :title="sortHeaderTitle('created_at')">
                <span>创建时间</span>
                <span v-if="sortRuleFor('created_at')" class="sort-state">
                  {{ sortRuleFor('created_at').order }} {{ sortRuleFor('created_at').direction === 'asc' ? 'ASC' : 'DESC' }}
                </span>
              </button>
            </template>
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="挂载源" width="120" class-name="hide-sm" label-class-name="hide-sm">
            <template #header>
              <button class="sort-header" @click="handleSortHeaderClick('mount_name')" @contextmenu.prevent="handleSortHeaderContextMenu('mount_name')" :title="sortHeaderTitle('mount_name')">
                <span>挂载源</span>
                <span v-if="sortRuleFor('mount_name')" class="sort-state">
                  {{ sortRuleFor('mount_name').order }} {{ sortRuleFor('mount_name').direction === 'asc' ? 'ASC' : 'DESC' }}
                </span>
              </button>
            </template>
            <template #default="{ row }">{{ search.searched ? row.mount_name : currentMountName }}</template>
          </el-table-column>
          <el-table-column label="创建者" width="120" class-name="hide-sm" label-class-name="hide-sm">
            <template #header>
              <button class="sort-header" @click="handleSortHeaderClick('creator')" @contextmenu.prevent="handleSortHeaderContextMenu('creator')" :title="sortHeaderTitle('creator')">
                <span>创建者</span>
                <span v-if="sortRuleFor('creator')" class="sort-state">
                  {{ sortRuleFor('creator').order }} {{ sortRuleFor('creator').direction === 'asc' ? 'ASC' : 'DESC' }}
                </span>
              </button>
            </template>
            <template #default="{ row }">{{ search.searched ? (row.mount_owner || '-') : currentMountOwner }}</template>
          </el-table-column>
          <el-table-column label="操作" width="132" fixed="right" align="center" class-name="operation-column">
            <template #default="{ row }">
              <div class="row-actions" @click.stop @dblclick.stop>
                <el-tooltip v-if="!row.is_dir" content="下载" placement="top" :show-after="250">
                  <el-button
                    class="action-button"
                    text
                    :icon="Download"
                    aria-label="下载"
                    @click="handleDownload(row)"
                  />
                </el-tooltip>
                <el-tooltip v-if="canPreview(row)" content="预览" placement="top" :show-after="250">
                  <el-button
                    class="action-button"
                    text
                    :icon="View"
                    aria-label="预览"
                    @click="handlePreview(row)"
                  />
                </el-tooltip>
                <el-dropdown trigger="click" placement="bottom-end" @command="(command) => handleRowCommand(command, row)">
                  <el-button class="action-button" text :icon="MoreFilled" aria-label="更多操作" />
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="rename" :icon="Edit">重命名</el-dropdown-item>
                      <el-dropdown-item command="move">移动</el-dropdown-item>
                      <el-dropdown-item class="danger-action" command="delete" :icon="Delete" divided>删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <!-- 网格视图 -->
        <div v-if="files.viewMode === 'grid' && displayFiles.length" class="file-grid">
          <div v-for="file in displayFiles" :key="file.path" class="file-card"
               :class="{ selected: isFileSelected(file) || fileKey(files.selectedFile) === fileKey(file) }"
               @dblclick="handleDblClick(file)"
               @click="handleFileClick(file, null, $event)"
               @contextmenu.prevent="onCardContextMenu($event, file)">
            <div v-if="batchMode" class="card-checkbox">
              <el-checkbox :model-value="isFileSelected(file)" @click.stop="toggleFileSelection(file)" />
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
        @close="files.selectFile(null)"
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
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Document, Download, Edit, Folder, FolderAdd, MoreFilled, UploadFilled, View } from '@element-plus/icons-vue'
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
const router = useRouter()
const files = useFilesStore()
const mounts = useMountsStore()
const upload = useUpload()
const search = useSearchStore()

const contextMenuRef = ref()
const fileTableRef = ref()
const dragging = ref(false)
const showPreview = ref(false)
const previewFile = ref(null)
const clipboard = ref(null) // { action: 'copy'|'cut', file: FileInfo }
const batchMode = ref(false)
const selectedFiles = ref([])
const selectionAnchorKey = ref('')
const focusedFileKey = ref('')
const syncingTableSelection = ref(false)

const currentMount = computed(() => mounts.mounts.find((m) => m.id === files.currentMountId) || null)
const canWriteCurrentMount = computed(() => currentMount.value?.my_level === 'readwrite')
const emptyState = computed(() => {
  if (!mounts.mounts.length) {
    return {
      description: '暂无可访问的挂载点',
      actionText: '去添加挂载',
      action: () => router.push('/mounts'),
    }
  }
  if (!files.currentMountId) {
    return { description: '请选择一个挂载点开始浏览' }
  }
  if (currentMount.value?.status === 'offline') {
    return { description: '当前挂载离线，文件列表可能不可用' }
  }
  if (files.sortedFiles.length === 0) {
    return {
      description: '此目录为空',
      actionText: canWriteCurrentMount.value ? '新建文件夹' : '',
      action: canWriteCurrentMount.value ? handleMkdir : null,
    }
  }
  return null
})

// 当前挂载名称（用于列表视图的挂载源列）
const currentMountName = computed(() => {
  const m = mounts.mounts.find((m) => m.id === files.currentMountId)
  return m?.name || '-'
})

const currentMountOwner = computed(() => currentMount.value?.owner_name || '-')
const sortFallback = computed(() => ({
  mount_name: currentMountName.value === '-' ? '' : currentMountName.value,
  creator: currentMountOwner.value === '-' ? '' : currentMountOwner.value,
}))
const sortedSearchResults = computed(() => files.sortEntries(search.filteredResults, sortFallback.value))
const displayFiles = computed(() => (search.searched ? sortedSearchResults.value : files.pagedFiles))
const selectionActive = computed(() => batchMode.value || selectedFiles.value.length > 1)

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

function sortRuleFor(field) {
  return files.getSortRule(field)
}

function sortHeaderTitle(field) {
  const rule = sortRuleFor(field)
  if (!rule) return '点击加入排序关键字'
  return `第 ${rule.order} 关键字，${rule.direction === 'asc' ? '升序' : '降序'}；右键取消`
}

function handleSortHeaderClick(field) {
  files.toggleSortField(field)
}

function handleSortHeaderContextMenu(field) {
  files.removeSortField(field)
}

function handleRowCommand(command, row) {
  if (command === 'rename') handleRename(row)
  else if (command === 'move') handleMove(row)
  else if (command === 'delete') handleDelete(row)
}

function fileKey(file) {
  if (!file) return ''
  return `${file.mount_id || files.currentMountId || ''}:${file.path}`
}

function isFileSelected(file) {
  const key = fileKey(file)
  return selectedFiles.value.some((item) => fileKey(item) === key)
}

function tableRowClassName({ row }) {
  return isFileSelected(row) ? 'selected-row' : ''
}

function syncTableSelection() {
  nextTick(() => {
    if (!fileTableRef.value) return
    syncingTableSelection.value = true
    fileTableRef.value.clearSelection?.()
    for (const file of selectedFiles.value) {
      const visible = displayFiles.value.find((item) => fileKey(item) === fileKey(file))
      if (visible) fileTableRef.value.toggleRowSelection?.(visible, true)
    }
    nextTick(() => {
      syncingTableSelection.value = false
    })
  })
}

function setSelectedFiles(nextSelection, anchorFile = null) {
  selectedFiles.value = nextSelection
  if (anchorFile) {
    selectionAnchorKey.value = fileKey(anchorFile)
    focusedFileKey.value = fileKey(anchorFile)
    files.selectFile(anchorFile)
  } else if (nextSelection.length === 1) {
    selectionAnchorKey.value = fileKey(nextSelection[0])
    focusedFileKey.value = fileKey(nextSelection[0])
    files.selectFile(nextSelection[0])
  } else if (nextSelection.length === 0) {
    selectionAnchorKey.value = ''
    focusedFileKey.value = ''
    files.selectFile(null)
  }
  syncTableSelection()
}

function clearSelection() {
  setSelectedFiles([])
}

function selectRangeTo(file) {
  const items = displayFiles.value
  const targetIndex = items.findIndex((item) => fileKey(item) === fileKey(file))
  if (targetIndex === -1) return
  const anchorIndex = items.findIndex((item) => fileKey(item) === selectionAnchorKey.value)
  const start = anchorIndex === -1 ? targetIndex : Math.min(anchorIndex, targetIndex)
  const end = anchorIndex === -1 ? targetIndex : Math.max(anchorIndex, targetIndex)
  setSelectedFiles(items.slice(start, end + 1), file)
}

function handleFileClick(file, _column, event = {}) {
  if (!file) return
  const additive = event.ctrlKey || event.metaKey
  if (event.shiftKey) {
    selectRangeTo(file)
  } else if (additive || batchMode.value) {
    toggleFileSelection(file)
  } else {
    setSelectedFiles([file], file)
  }
}

// 批量选择模式切换
function toggleBatchMode() {
  batchMode.value = !batchMode.value
  if (!batchMode.value) clearSelection()
}

// 表格 selection-change 回调
function handleSelectionChange(rows) {
  if (syncingTableSelection.value) return
  if (!batchMode.value) return
  selectedFiles.value = rows
  const last = rows.at(-1)
  if (last) {
    selectionAnchorKey.value = fileKey(last)
    focusedFileKey.value = fileKey(last)
    files.selectFile(last)
  }
}

// 网格视图切换选中
function toggleFileSelection(file) {
  const key = fileKey(file)
  const nextSelection = [...selectedFiles.value]
  const idx = nextSelection.findIndex((f) => fileKey(f) === key)
  if (idx >= 0) nextSelection.splice(idx, 1)
  else nextSelection.push(file)
  setSelectedFiles(nextSelection, idx >= 0 ? (nextSelection.at(-1) || null) : file)
}

function isTypingTarget(target) {
  const tag = target?.tagName?.toLowerCase()
  return tag === 'input' || tag === 'textarea' || tag === 'select' || target?.isContentEditable
}

function focusedIndex() {
  const items = displayFiles.value
  const key = focusedFileKey.value || fileKey(files.selectedFile) || fileKey(selectedFiles.value.at(-1))
  const index = items.findIndex((item) => fileKey(item) === key)
  return index === -1 ? 0 : index
}

function moveFocus(delta, extendSelection = false) {
  const items = displayFiles.value
  if (!items.length) return
  const nextIndex = Math.min(items.length - 1, Math.max(0, focusedIndex() + delta))
  const file = items[nextIndex]
  if (extendSelection) {
    if (!selectionAnchorKey.value) selectionAnchorKey.value = fileKey(files.selectedFile || selectedFiles.value.at(-1) || items[focusedIndex()])
    selectRangeTo(file)
  } else {
    setSelectedFiles([file], file)
  }
}

function handleFileBrowserKeydown(event) {
  if (document.querySelector('.el-overlay-dialog, .el-overlay-message-box')) return
  if (isTypingTarget(event.target) || !displayFiles.value.length) return

  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') {
    event.preventDefault()
    setSelectedFiles([...displayFiles.value], displayFiles.value[displayFiles.value.length - 1])
    return
  }

  if (event.key === 'Escape') {
    event.preventDefault()
    clearSelection()
    return
  }

  if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
    event.preventDefault()
    moveFocus(1, event.shiftKey)
    return
  }

  if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
    event.preventDefault()
    moveFocus(-1, event.shiftKey)
    return
  }

  if (event.key === 'Home') {
    event.preventDefault()
    const first = displayFiles.value[0]
    if (event.shiftKey) selectRangeTo(first)
    else setSelectedFiles([first], first)
    return
  }

  if (event.key === 'End') {
    event.preventDefault()
    const last = displayFiles.value[displayFiles.value.length - 1]
    if (event.shiftKey) selectRangeTo(last)
    else setSelectedFiles([last], last)
    return
  }

  if (event.key === 'Enter') {
    const file = displayFiles.value.find((item) => fileKey(item) === focusedFileKey.value) || selectedFiles.value.at(-1)
    if (file) {
      event.preventDefault()
      handleDblClick(file)
    }
  }
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
  if (!canWriteCurrentMount.value) return ElMessage.warning('当前挂载没有写入权限')
  const { value } = await ElMessageBox.prompt('请输入文件夹名称', '新建文件夹', {
    inputValidator: (v) => !!v.trim() || '名称不能为空',
  })
  await createDirectory(files.currentMountId, files.currentPath + '/' + value.trim())
  ElMessage.success('已创建')
  files.refresh()
}

// 上传 (el-upload before-upload 钩子)
function handleUpload(file) {
  if (!canWriteCurrentMount.value) {
    ElMessage.warning('当前挂载没有上传权限')
    return false
  }
  upload.upload(files.currentMountId, files.currentPath, file).then(() => files.refresh())
  return false // 阻止 el-upload 自动上传
}

// ── 拖拽上传 ──────────────────────────────────────────────
let dragCounter = 0
function onDragEnter() { dragCounter++; dragging.value = true }
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
    if (!canWriteCurrentMount.value) {
      ElMessage.warning('当前挂载没有上传权限')
      return
    }
    upload.uploadMultiple(files.currentMountId, files.currentPath, droppedFiles).then(() => files.refresh())
  }
}

// ── 右键菜单 ──────────────────────────────────────────────
function onRowContextMenu(row, column, event) {
  if (!isFileSelected(row)) setSelectedFiles([row], row)
  else files.selectFile(row)
  contextMenuRef.value.open(event, row)
}
function onCardContextMenu(event, file) {
  if (!isFileSelected(file)) setSelectedFiles([file], file)
  else files.selectFile(file)
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
    const url = `${location.origin}/share/${res.token}`
    await navigator.clipboard.writeText(url)
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
    clearSelection()
    search.query = q
    nextTick(() => search.search())
  }
}, { immediate: true })

watch(() => [files.currentMountId, files.currentPath, files.page, search.searched], () => {
  clearSelection()
})

watch(() => displayFiles.value.map(fileKey).join('|'), () => {
  const visibleKeys = new Set(displayFiles.value.map(fileKey))
  const visibleSelection = selectedFiles.value.filter((file) => visibleKeys.has(fileKey(file)))
  if (visibleSelection.length !== selectedFiles.value.length) {
    setSelectedFiles(visibleSelection)
  } else {
    syncTableSelection()
  }
})

// 初始化: 默认加载第一个挂载点 (非搜索模式)
onMounted(async () => {
  window.addEventListener('keydown', handleFileBrowserKeydown)
  await mounts.fetchMounts()
  if (!route.query.q && mounts.mounts.length > 0) {
    files.fetchFiles(mounts.mounts[0].id, '/')
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleFileBrowserKeydown)
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
.batch-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; background: rgba(64,158,255,0.08); border: 1px solid rgba(64,158,255,0.18);
  border-radius: 8px; color: var(--text-regular); font-size: 13px;
}
.batch-actions { display: flex; align-items: center; gap: 8px; }
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
:deep(.selected-row > td) {
  background: rgba(64,158,255,0.08) !important;
}
:deep(.selected-row:hover > td) {
  background: rgba(64,158,255,0.12) !important;
}
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
  position: fixed; bottom: 20px; right: 20px; left: calc(var(--sidebar-width, 240px) + 40px); z-index: 200;
  display: flex; align-items: center; gap: 12px; padding: 12px 16px;
  background: var(--card-bg); border-radius: 10px; box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  font-size: 13px;
}

/* 搜索工具栏 */
.search-toolbar {
  padding: 12px 16px; background: var(--card-bg); border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06); display: flex; flex-direction: column; gap: 8px;
}
.search-filters { align-items: center; }
.search-meta { display: flex; align-items: center; justify-content: space-between; font-size: 13px; color: var(--text-secondary); }
.sort-header {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.sort-state {
  flex: 0 0 auto;
  font-size: 11px;
  line-height: 1;
  color: var(--primary-color);
}
.row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  min-height: 32px;
  white-space: nowrap;
}
.row-actions :deep(.el-dropdown) {
  display: inline-flex;
}
.action-button {
  width: 30px;
  height: 30px;
  padding: 0;
  border-radius: 6px;
  color: var(--el-color-primary);
}
.action-button:hover,
.action-button:focus-visible {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
:deep(.danger-action) {
  color: var(--el-color-danger);
  font-weight: 600;
}
:deep(.danger-action .el-icon) {
  color: var(--el-color-danger);
}
:deep(.danger-action:hover),
:deep(.danger-action:focus) {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}
:deep(.operation-column .cell) {
  padding-left: 8px;
  padding-right: 8px;
  overflow: visible;
}

@media (max-width: 768px) {
  .file-browser { gap: 10px; }
  .file-toolbar {
    align-items: flex-start;
    gap: 10px;
    flex-direction: column;
    padding: 10px 12px;
  }
  .file-toolbar :deep(.el-breadcrumb) {
    max-width: 100%;
    overflow: hidden;
  }
  .toolbar-actions {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr 1fr auto;
  }
  .toolbar-actions :deep(.el-button),
  .toolbar-actions :deep(.el-upload),
  .toolbar-actions :deep(.el-upload .el-button) {
    width: 100%;
  }
  .batch-toolbar {
    position: sticky;
    top: 0;
    z-index: 10;
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }
  .batch-actions {
    width: 100%;
    justify-content: flex-end;
    flex-wrap: wrap;
  }
  .file-content-wrapper { display: block; }
  .file-content { padding: 10px; }
  .file-grid { grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: 8px; }
  .file-card { padding: 12px 6px; min-height: 112px; }
  .upload-bar {
    left: 12px;
    right: 12px;
    bottom: 72px;
    flex-direction: column;
    align-items: stretch;
  }
  .search-toolbar { padding: 10px 12px; }
  .search-filters > * { flex: 1 1 140px; }
  :deep(.operation-column .cell) {
    padding-left: 4px;
    padding-right: 4px;
  }
  .row-actions {
    gap: 2px;
  }
  .action-button {
    width: 28px;
    height: 28px;
  }
}
</style>
