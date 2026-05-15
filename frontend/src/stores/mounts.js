import { defineStore } from 'pinia'
import { listMounts as listMountsApi, createMount as createMountApi, deleteMount as deleteMountApi, testConnection as testConnectionApi } from '@/api/mounts'

export const useMountsStore = defineStore('mounts', {
  state: () => ({
    mounts: [],
    loading: false,
  }),

  getters: {
    onlineMounts: (state) => state.mounts.filter((m) => m.status === 'online'),
    offlineMounts: (state) => state.mounts.filter((m) => m.status === 'offline'),
  },

  actions: {
    async fetchMounts() {
      this.loading = true
      try {
        this.mounts = await listMountsApi()
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
      return await testConnectionApi(id)
    },
  },
})
