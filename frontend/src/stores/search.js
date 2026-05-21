/**
 * File search state: indexed search, advanced filters, and refresh state.
 */
import { defineStore } from 'pinia'
import { refreshSearchIndex, searchFiles } from '@/api/search'

export const useSearchStore = defineStore('search', {
  state: () => ({
    query: '',
    useRegex: false,
    filterByMount: '',
    filterByOwner: '',
    fileType: '',
    extension: '',
    pathPrefix: '',
    sizeMin: null,
    sizeMax: null,
    modifiedFrom: '',
    modifiedTo: '',
    results: [],
    loading: false,
    indexing: false,
    searched: false,
    error: '',
    indexSummary: null,
  }),

  getters: {
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

    availableMounts(state) {
      return [...new Set(state.results.map((r) => r.mount_name).filter(Boolean))]
    },

    availableOwners(state) {
      return [...new Set(state.results.map((r) => r.mount_owner).filter(Boolean))]
    },
  },

  actions: {
    searchParams() {
      const params = {
        q: this.query,
        regex: this.useRegex,
        limit: 200,
      }
      if (this.fileType) params.file_type = this.fileType
      if (this.extension.trim()) params.extension = this.extension.trim()
      if (this.pathPrefix.trim()) params.path_prefix = this.pathPrefix.trim()
      if (this.sizeMin !== null && this.sizeMin !== '') params.size_min = Number(this.sizeMin)
      if (this.sizeMax !== null && this.sizeMax !== '') params.size_max = Number(this.sizeMax)
      if (this.modifiedFrom) params.modified_from = new Date(this.modifiedFrom).toISOString()
      if (this.modifiedTo) params.modified_to = new Date(this.modifiedTo).toISOString()
      if (this.filterByOwner) params.owner = this.filterByOwner
      return params
    },

    async search() {
      if (!this.query.trim()) return
      this.loading = true
      this.searched = true
      this.error = ''
      try {
        this.results = await searchFiles(this.searchParams())
      } catch (e) {
        this.results = []
        this.error = e.response?.data?.detail || '搜索失败'
      } finally {
        this.loading = false
      }
    },

    async refreshIndex() {
      this.indexing = true
      this.error = ''
      try {
        this.indexSummary = await refreshSearchIndex({})
        if (this.query.trim()) await this.search()
      } catch (e) {
        this.error = e.response?.data?.detail || '索引刷新失败'
      } finally {
        this.indexing = false
      }
    },

    clearSearch() {
      this.query = ''
      this.useRegex = false
      this.filterByMount = ''
      this.filterByOwner = ''
      this.fileType = ''
      this.extension = ''
      this.pathPrefix = ''
      this.sizeMin = null
      this.sizeMax = null
      this.modifiedFrom = ''
      this.modifiedTo = ''
      this.results = []
      this.searched = false
      this.loading = false
      this.error = ''
      this.indexSummary = null
    },
  },
})
