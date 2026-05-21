/**
 * 文件浏览器状态管理 — 当前挂载点、路径、文件列表、视图模式、选中项、分页。
 */
import { defineStore } from 'pinia'
import { listFiles } from '@/api/files'

const SORT_STORAGE_KEY = 'mounthubFileSortRules'

function loadSortRules() {
  try {
    const saved = JSON.parse(localStorage.getItem(SORT_STORAGE_KEY) || '[]')
    return Array.isArray(saved) ? saved : []
  } catch {
    return []
  }
}

export const useFilesStore = defineStore('files', {
  state: () => ({
    currentMountId: null,   // 当前挂载点 ID
    currentPath: '/',       // 当前浏览路径
    files: [],              // 当前目录文件列表
    selectedFile: null,     // 右侧详情面板选中的文件
    viewMode: 'list',       // list | grid
    sortBy: 'name',         // 兼容旧入口: name | size | modified
    sortRules: loadSortRules(),
    loading: false,
    error: '',
    page: 1,                // 当前页码
    pageSize: 100,          // 每页数量
  }),

  getters: {
    /** 按当前排序方式排列文件, 目录始终在前 */
    sortedFiles(state) {
      return sortFileEntries(state.files, state.sortRules)
    },

    /** 分页后的文件列表 */
    pagedFiles() {
      const start = (this.page - 1) * this.pageSize
      return this.sortedFiles.slice(start, start + this.pageSize)
    },

    /** 总页数 */
    totalPages() {
      return Math.max(1, Math.ceil(this.sortedFiles.length / this.pageSize))
    },
  },

  actions: {
    /** 加载指定路径的文件列表 */
    async fetchFiles(mountId, path = '/') {
      this.loading = true
      this.currentMountId = mountId
      this.currentPath = path
      this.page = 1
      this.error = ''
      try {
        this.files = await listFiles(mountId, path)
      } catch (e) {
        this.files = []
        this.error = e.response?.data?.detail || '文件列表加载失败'
      } finally {
        this.loading = false
      }
    },

    /** 刷新当前目录 */
    async refresh() {
      if (this.currentMountId) {
        await this.fetchFiles(this.currentMountId, this.currentPath)
      }
    },

    setPage(p) {
      this.page = p
    },

    selectFile(file) {
      this.selectedFile = file
    },

    setViewMode(mode) {
      this.viewMode = mode
    },

    setSortBy(field) {
      this.sortBy = field
      const normalized = field === 'modified' ? 'modified_at' : field
      this.sortRules = [{ field: normalized, direction: 'asc' }]
      this.persistSortRules()
      this.page = 1
    },

    toggleSortField(field) {
      const existing = this.sortRules.find((rule) => rule.field === field)
      if (existing) {
        existing.direction = existing.direction === 'asc' ? 'desc' : 'asc'
      } else {
        this.sortRules.push({ field, direction: 'asc' })
      }
      this.persistSortRules()
      this.page = 1
    },

    removeSortField(field) {
      this.sortRules = this.sortRules.filter((rule) => rule.field !== field)
      this.persistSortRules()
      this.page = 1
    },

    persistSortRules() {
      localStorage.setItem(SORT_STORAGE_KEY, JSON.stringify(this.sortRules))
    },

    getSortRule(field) {
      const index = this.sortRules.findIndex((rule) => rule.field === field)
      if (index === -1) return null
      return { ...this.sortRules[index], order: index + 1 }
    },

    sortEntries(entries, fallback = {}) {
      return sortFileEntries(entries, this.sortRules, fallback)
    },
  },
})

function sortFileEntries(entries, sortRules = [], fallback = {}) {
  const rules = sortRules.length ? sortRules : [{ field: 'name', direction: 'asc' }]
  return [...entries].sort((a, b) => {
    if (a.is_dir !== b.is_dir) return b.is_dir ? 1 : -1

    for (const rule of rules) {
      const result = compareField(a, b, rule.field, fallback)
      if (result !== 0) return rule.direction === 'desc' ? -result : result
    }

    return compareString(a.name, b.name)
  })
}

function compareField(a, b, field, fallback) {
  if (field === 'size') return compareNumber(a.size, b.size)
  if (field === 'modified_at' || field === 'created_at') {
    return compareTime(a[field], b[field])
  }
  return compareString(getTextValue(a, field, fallback), getTextValue(b, field, fallback))
}

function getTextValue(row, field, fallback) {
  if (field === 'mount_name') return row.mount_name || fallback.mount_name || ''
  if (field === 'creator') return row.mount_owner || row.creator || fallback.creator || ''
  return row[field] || ''
}

function compareString(a, b) {
  return String(a || '').localeCompare(String(b || ''), 'zh-CN', {
    numeric: true,
    sensitivity: 'base',
  })
}

function compareNumber(a, b) {
  return (Number(a) || 0) - (Number(b) || 0)
}

function compareTime(a, b) {
  const left = a ? new Date(a).getTime() : 0
  const right = b ? new Date(b).getTime() : 0
  return left - right
}
