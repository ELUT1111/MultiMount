import { defineStore } from 'pinia'
import { login as loginApi } from '@/api/auth'

function safeParseUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
}

const ADMIN_ROLE_NAMES = ['admin', 'super_admin']

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: localStorage.getItem('access_token') || '',
    refreshToken: localStorage.getItem('refresh_token') || '',
    user: safeParseUser(),
  }),

  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    username: (state) => state.user?.username || '',
    isAdmin: (state) => ADMIN_ROLE_NAMES.includes(state.user?.role?.name),
    isSuperAdmin: (state) => state.user?.role?.name === 'super_admin',
  },

  actions: {
    async refreshUser() {
      if (!this.accessToken) return null
      const { getMe } = await import('@/api/users')
      const user = await getMe()
      this.user = user
      localStorage.setItem('user', JSON.stringify(user))
      return user
    },

    async login(loginId, password) {
      const data = await loginApi({ login_id: loginId, password })
      this.accessToken = data.access_token
      this.refreshToken = data.refresh_token
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      // 获取用户信息
      try {
        await this.refreshUser()
      } catch {
        this.user = { username: loginId }
        localStorage.setItem('user', JSON.stringify({ username: loginId }))
      }
    },

    logout() {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
    },
  },
})
