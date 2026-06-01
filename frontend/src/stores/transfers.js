import { defineStore } from 'pinia'
import { listTransfers, pauseTransfer, resumeTransfer, cancelTransfer, retryTransfer } from '@/api/transfers'

let localTaskSeq = 0
const localTaskCancels = new Map()

function isLocalTaskId(id) {
  return typeof id === 'string' && id.startsWith('local-')
}

function nowIso() {
  return new Date().toISOString()
}

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
        const localTasks = this.tasks.filter((task) => isLocalTaskId(task.id))
        const remoteTasks = await listTransfers()
        this.tasks = [...localTasks, ...remoteTasks]
      } catch {
        // Keep the transfer page usable when a refresh fails.
      } finally {
        this.loading = false
      }
    },

    async pauseTask(id) {
      if (isLocalTaskId(id)) return
      await pauseTransfer(id)
      await this.fetchTasks()
    },

    async resumeTask(id) {
      if (isLocalTaskId(id)) return
      await resumeTransfer(id)
      await this.fetchTasks()
    },

    async cancelTask(id) {
      if (isLocalTaskId(id)) {
        const task = this.tasks.find((item) => item.id === id)
        if (!task) return
        if (['completed', 'failed'].includes(task.status)) {
          this.tasks = this.tasks.filter((item) => item.id !== id)
          localTaskCancels.delete(id)
          return
        }
        const cancel = localTaskCancels.get(id)
        if (cancel) cancel()
        this.updateLocalTask(id, {
          status: 'failed',
          speed: 0,
          error_message: '已取消',
        })
        localTaskCancels.delete(id)
        return
      }
      await cancelTransfer(id)
      await this.fetchTasks()
    },

    async retryTask(id) {
      if (isLocalTaskId(id)) return
      await retryTransfer(id)
      await this.fetchTasks()
    },

    updateTaskProgress(payload) {
      const idx = this.tasks.findIndex((t) => t.id === payload.task_id)
      if (idx >= 0) {
        this.tasks[idx] = { ...this.tasks[idx], ...payload }
      }
    },

    createDownloadTask({ mountId, fileName, fileSize = 0, sourcePath, targetPath = '浏览器下载', cancel }) {
      const id = `local-download-${Date.now()}-${++localTaskSeq}`
      const task = {
        id,
        user_id: null,
        type: 'download',
        status: 'running',
        file_name: fileName || sourcePath?.split('/').filter(Boolean).pop() || '下载文件',
        file_size: fileSize || 0,
        source_path: sourcePath || '/',
        target_path: targetPath,
        mount_id: mountId,
        source_mount_id: mountId,
        target_mount_id: null,
        conflict_policy: 'rename',
        transferred: 0,
        chunk_size: 0,
        speed: 0,
        error_message: null,
        created_at: nowIso(),
        updated_at: nowIso(),
        local: true,
      }
      if (cancel) localTaskCancels.set(id, cancel)
      this.tasks = [task, ...this.tasks]
      return task
    },

    updateLocalTask(id, patch) {
      const idx = this.tasks.findIndex((task) => task.id === id)
      if (idx < 0) return
      this.tasks[idx] = {
        ...this.tasks[idx],
        ...patch,
        updated_at: nowIso(),
      }
    },

    completeLocalTask(id, patch = {}) {
      const task = this.tasks.find((item) => item.id === id)
      if (!task) return
      const fileSize = patch.file_size || patch.fileSize || task.file_size || task.transferred
      this.updateLocalTask(id, {
        ...patch,
        status: 'completed',
        file_size: fileSize,
        transferred: fileSize || task.transferred,
        speed: 0,
        error_message: null,
      })
      localTaskCancels.delete(id)
    },

    failLocalTask(id, message = '下载失败') {
      this.updateLocalTask(id, {
        status: 'failed',
        speed: 0,
        error_message: message,
      })
      localTaskCancels.delete(id)
    },
  },
})
