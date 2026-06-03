import { defineStore } from 'pinia'
import { getWebDAVStatus, startWebDAV, stopWebDAV, updateWebDAVConfig } from '@/api/webdav'

const defaultConfig = () => ({
  host: '0.0.0.0',
  port: 8080,
  ssl: false,
  root_mount: '',
  access_log: true,
  log_path: '/var/log/webdav/access.log',
  recycle_delete: true,
  url: 'http://localhost:8080/',
})

function applyStatus(config, status) {
  config.host = status.host || '0.0.0.0'
  config.port = status.port || 8080
  config.ssl = status.ssl || false
  config.root_mount = status.root_mount || ''
  config.access_log = status.access_log ?? true
  config.log_path = status.log_path || '/var/log/webdav/access.log'
  config.recycle_delete = status.recycle_delete ?? true
  config.url = status.url || `${config.ssl ? 'https' : 'http'}://localhost:${config.port}/`
}

export const useWebDAVStore = defineStore('webdav', {
  state: () => ({
    running: false,
    loading: false,
    loaded: false,
    config: defaultConfig(),
  }),

  actions: {
    payload() {
      return {
        host: this.config.host,
        port: this.config.port,
        ssl: this.config.ssl,
        root_mount: this.config.root_mount || null,
        access_log: this.config.access_log,
        log_path: this.config.log_path,
        recycle_delete: this.config.recycle_delete,
      }
    },

    async fetchStatus() {
      const status = await getWebDAVStatus()
      this.running = status.running
      applyStatus(this.config, status)
      this.loaded = true
      return status
    },

    async start(config = null) {
      this.loading = true
      const previous = this.running
      this.running = true
      try {
        const status = await startWebDAV(config || this.payload())
        this.running = status.running
        applyStatus(this.config, status)
        this.loaded = true
        return status
      } catch (error) {
        this.running = previous
        throw error
      } finally {
        this.loading = false
      }
    },

    async stop() {
      this.loading = true
      const previous = this.running
      this.running = false
      try {
        const status = await stopWebDAV()
        this.running = status.running
        applyStatus(this.config, status)
        this.loaded = true
        return status
      } catch (error) {
        this.running = previous
        throw error
      } finally {
        this.loading = false
      }
    },

    async saveConfig(config = null) {
      this.loading = true
      try {
        const status = await updateWebDAVConfig(config || this.payload())
        this.running = status.running
        applyStatus(this.config, status)
        this.loaded = true
        return status
      } finally {
        this.loading = false
      }
    },
  },
})
