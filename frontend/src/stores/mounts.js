import { defineStore } from 'pinia'
import { listMounts as listMountsApi, createMount as createMountApi, deleteMount as deleteMountApi, testConnection as testConnectionApi } from '@/api/mounts'

export const useMountsStore = defineStore('mounts', {
  state: () => ({
    mounts: [],
    loading: false,
    loaded: false, // 是否已加载过数据
  }),

  getters: {
    onlineMounts: (state) => state.mounts.filter((m) => m.status === 'online'),
    offlineMounts: (state) => state.mounts.filter((m) => m.status === 'offline'),
    accessibleMounts: (state) => state.mounts.filter((m) => ['read', 'readwrite'].includes(m.my_level)),
  },

  actions: {
    /** 加载挂载列表, force=true 强制刷新 */
    async fetchMounts(force = false) {
      if (this.loaded && !force) return
      this.loading = true
      try {
        this.mounts = await listMountsApi()
        this.loaded = true
      } finally {
        this.loading = false
      }
    },

    async addMount(data) {
      const mount = await createMountApi(data)
      this.mounts.push(mount)
      return mount
    },

    async removeMount(id) {
      await deleteMountApi(id)
      this.mounts = this.mounts.filter((m) => m.id !== id)
    },

    async testMount(id) {
      const result = await testConnectionApi(id)
      const index = this.mounts.findIndex((m) => m.id === id)
      if (index !== -1) {
        this.mounts[index] = {
          ...this.mounts[index],
          status: result.success ? 'online' : 'offline',
          last_connected_at: result.success
            ? new Date().toISOString()
            : this.mounts[index].last_connected_at,
        }
      }
      return result
    },
  },
})
