import { defineStore } from 'pinia'
import { listTransfers, pauseTransfer, resumeTransfer, cancelTransfer, retryTransfer } from '@/api/transfers'

export const useTransfersStore = defineStore('transfers', {
  state: () => ({
    tasks: [],
    loading: false,
    activeTab: 'running',
  }),

  getters: {
    filteredTasks(state) {
      if (state.activeTab === 'running') {
        return state.tasks.filter((t) => ['queued', 'pending', 'running', 'paused'].includes(t.status))
      }
      if (state.activeTab === 'completed') {
        return state.tasks.filter((t) => t.status === 'completed')
      }
      if (state.activeTab === 'failed') {
        return state.tasks.filter((t) => t.status === 'failed')
      }
      return state.tasks
    },

    totalTransferSpeed(state) {
      return state.tasks
        .filter((t) => t.status === 'running')
        .reduce((sum, t) => sum + (t.speed || 0), 0)
    },

    activeCount(state) {
      return state.tasks.filter((t) => t.status === 'running').length
    },
  },

  actions: {
    async fetchTasks() {
      this.loading = true
      try {
        this.tasks = await listTransfers()
      } catch {
        // Keep the transfer page usable when a refresh fails.
      } finally {
        this.loading = false
      }
    },

    async pauseTask(id) {
      await pauseTransfer(id)
      await this.fetchTasks()
    },

    async resumeTask(id) {
      await resumeTransfer(id)
      await this.fetchTasks()
    },

    async cancelTask(id) {
      await cancelTransfer(id)
      await this.fetchTasks()
    },

    async retryTask(id) {
      await retryTransfer(id)
      await this.fetchTasks()
    },

    updateTaskProgress(payload) {
      const idx = this.tasks.findIndex((t) => t.id === payload.task_id)
      if (idx >= 0) {
        this.tasks[idx] = { ...this.tasks[idx], ...payload }
      }
    },
  },
})
