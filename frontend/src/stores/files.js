/**
 * 文件浏览器状态管理 — 当前挂载点、路径、文件列表、视图模式、选中项。
 */
import { defineStore } from 'pinia'
import { listFiles } from '@/api/files'

export const useFilesStore = defineStore('files', {
  state: () => ({
    currentMountId: null,   // 当前挂载点 ID
    currentPath: '/',       // 当前浏览路径
    files: [],              // 当前目录文件列表
    selectedFile: null,     // 右侧详情面板选中的文件
    viewMode: 'list',       // list | grid
    sortBy: 'name',         // name | size | modified
    loading: false,
  }),

  getters: {
    /** 按当前排序方式排列文件, 目录始终在前 */
    sortedFiles(state) {
      const arr = [...state.files]
      arr.sort((a, b) => {
        // 目录优先
        if (a.is_dir !== b.is_dir) return b.is_dir ? 1 : -1
        if (state.sortBy === 'size') return a.size - b.size
        if (state.sortBy === 'modified') return (a.modified_at || '').localeCompare(b.modified_at || '')
        return a.name.localeCompare(b.name, 'zh-CN')
      })
      return arr
    },
  },

  actions: {
    /** 加载指定路径的文件列表 */
    async fetchFiles(mountId, path = '/') {
      this.loading = true
      this.currentMountId = mountId
      this.currentPath = path
      try {
        this.files = await listFiles(mountId, path)
      } catch {
        this.files = []
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

    selectFile(file) {
      this.selectedFile = file
    },

    setViewMode(mode) {
      this.viewMode = mode
    },

    setSortBy(field) {
      this.sortBy = field
    },
  },
})
