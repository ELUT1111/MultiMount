import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const service = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// 请求拦截: 注入 JWT
service.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截: 统一错误处理
service.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail || '请求失败'

    if (status === 401) {
      // 尝试刷新令牌
      const refresh = localStorage.getItem('refresh_token')
      if (refresh && !error.config._retry) {
        error.config._retry = true
        try {
          const { data } = await axios.post('/api/v1/auth/refresh', {
            refresh_token: refresh,
          })
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)
          error.config.headers.Authorization = `Bearer ${data.access_token}`
          return service(error.config)
        } catch {
          // 刷新失败, 跳转登录
        }
      }
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      router.push('/login')
    }

    ElMessage.error(detail)
    return Promise.reject(error)
  }
)

export default service
