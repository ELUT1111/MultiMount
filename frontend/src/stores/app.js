import { defineStore } from 'pinia'

const STORAGE_KEY = 'mounthubAppPreferences'

const defaultColumns = {
  size: { visible: true, width: 120, fixed: false },
  modified_at: { visible: true, width: 180, fixed: false },
  created_at: { visible: true, width: 180, fixed: false },
  mount_name: { visible: true, width: 120, fixed: false },
  creator: { visible: true, width: 120, fixed: false },
}

function loadPreferences() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

function systemTheme() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useAppStore = defineStore('app', {
  state: () => {
    const saved = loadPreferences()
    return {
      theme: saved.theme || localStorage.getItem('theme') || 'system',
      highContrast: !!saved.highContrast,
      compactMode: !!saved.compactMode,
      fileColumns: {
        ...defaultColumns,
        ...(saved.fileColumns || {}),
      },
    }
  },

  getters: {
    effectiveTheme(state) {
      return state.theme === 'system' ? systemTheme() : state.theme
    },
    isDark() {
      return this.effectiveTheme === 'dark'
    },
  },

  actions: {
    applyPreferences() {
      const root = document.documentElement
      root.classList.toggle('dark', this.isDark)
      root.classList.toggle('high-contrast', this.highContrast)
      root.classList.toggle('compact', this.compactMode)
      localStorage.setItem('theme', this.isDark ? 'dark' : 'light')
      this.persist()
    },
    persist() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        theme: this.theme,
        highContrast: this.highContrast,
        compactMode: this.compactMode,
        fileColumns: this.fileColumns,
      }))
    },
    setTheme(theme) {
      this.theme = theme
      this.applyPreferences()
    },
    toggleHighContrast() {
      this.highContrast = !this.highContrast
      this.applyPreferences()
    },
    toggleCompactMode() {
      this.compactMode = !this.compactMode
      this.applyPreferences()
    },
    updateFileColumn(key, patch) {
      this.fileColumns[key] = { ...defaultColumns[key], ...(this.fileColumns[key] || {}), ...patch }
      this.persist()
    },
    resetFileColumns() {
      this.fileColumns = { ...defaultColumns }
      this.persist()
    },
  },
})
