import { defineStore } from 'pinia'
import { login as loginApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: localStorage.getItem('access_token') || '',
    refreshToken: localStorage.getItem('refresh_token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
  }),

  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    username: (state) => state.user?.username || '',
  },

  actions: {
    async login(username, password) {
      const data = await loginApi({ username, password })
      this.accessToken = data.access_token
      this.refreshToken = data.refresh_token
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      // 获取用户信息
      try {
        const { getMe } = await import('@/api/users')
        const user = await getMe()
        this.user = user
        localStorage.setItem('user', JSON.stringify(user))
      } catch {
        this.user = { username }
        localStorage.setItem('user', JSON.stringify({ username }))
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
