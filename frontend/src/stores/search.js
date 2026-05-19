/**
 * 文件搜索状态管理 — 搜索结果、筛选条件、加载状态。
 */
import { defineStore } from 'pinia'
import { searchFiles } from '@/api/search'

export const useSearchStore = defineStore('search', {
  state: () => ({
    query: '',
    useRegex: false,
    filterByMount: '',
    filterByOwner: '',
    results: [],
    loading: false,
    searched: false,
    error: '',
  }),

  getters: {
    /** 按挂载源 + 创建者二次过滤 */
    filteredResults(state) {
      let arr = state.results
      if (state.filterByMount) {
        arr = arr.filter((r) => r.mount_name === state.filterByMount)
      }
      if (state.filterByOwner) {
        arr = arr.filter((r) => r.mount_owner === state.filterByOwner)
      }
      return arr
    },

    /** 结果中不重复的挂载名列表 */
    availableMounts(state) {
      return [...new Set(state.results.map((r) => r.mount_name).filter(Boolean))]
    },

    /** 结果中不重复的创建者列表 */
    availableOwners(state) {
      return [...new Set(state.results.map((r) => r.mount_owner).filter(Boolean))]
    },
  },

  actions: {
    async search() {
      if (!this.query.trim()) return
      this.loading = true
      this.searched = true
      this.error = ''
      try {
        const params = { q: this.query, regex: this.useRegex, limit: 200 }
        this.results = await searchFiles(params)
      } catch (e) {
        this.results = []
        this.error = e.response?.data?.detail || '搜索失败'
      } finally {
        this.loading = false
      }
    },

    clearSearch() {
      this.query = ''
      this.useRegex = false
      this.filterByMount = ''
      this.filterByOwner = ''
      this.results = []
      this.searched = false
      this.loading = false
      this.error = ''
    },
  },
})
