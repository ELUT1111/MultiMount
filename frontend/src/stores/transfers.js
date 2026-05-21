/**
 * 传输任务状态管理 — 任务列表、按状态过滤、WebSocket 进度更新。
 */
import { defineStore } from 'pinia'
import { listTransfers, pauseTransfer, resumeTransfer, cancelTransfer, retryTransfer } from '@/api/transfers'

export const useTransfersStore = defineStore('transfers', {
  state: () => ({
    tasks: [],          // 全部任务
    loading: false,
    activeTab: 'running', // 当前标签: running / completed / failed
  }),

  getters: {
    /** 按状态过滤任务列表 */
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

    /** 当前总上传速度 */
    totalUploadSpeed(state) {
      return state.tasks
        .filter((t) => t.type === 'upload' && t.status === 'running')
        .reduce((sum, t) => sum + (t.speed || 0), 0)
    },

    /** 当前总下载速度 */
    totalDownloadSpeed(state) {
      return state.tasks
        .filter((t) => t.type === 'download' && t.status === 'running')
        .reduce((sum, t) => sum + (t.speed || 0), 0)
    },

    /** 并发任务数 */
    activeCount(state) {
      return state.tasks.filter((t) => t.status === 'running').length
    },
  },

  actions: {
    /** 拉取任务列表 */
    async fetchTasks() {
      this.loading = true
      try {
        this.tasks = await listTransfers()
      } catch {
        // 静默失败
      } finally {
        this.loading = false
      }
    },

    /** 暂停任务 */
    async pauseTask(id) {
      await pauseTransfer(id)
      await this.fetchTasks()
    },

    /** 恢复任务 */
    async resumeTask(id) {
      await resumeTransfer(id)
      await this.fetchTasks()
    },

    /** 取消任务 */
    async cancelTask(id) {
      await cancelTransfer(id)
      await this.fetchTasks()
    },

    /** 重试任务 */
    async retryTask(id) {
      await retryTransfer(id)
      await this.fetchTasks()
    },

    /** 通过 WebSocket 进度更新更新单个任务 (无需重新拉取整个列表) */
    updateTaskProgress(payload) {
      const idx = this.tasks.findIndex((t) => t.id === payload.task_id)
      if (idx >= 0) {
        this.tasks[idx] = { ...this.tasks[idx], ...payload }
      }
    },
  },
})
