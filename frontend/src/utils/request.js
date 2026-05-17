import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const service = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// 上传专用实例 (更长超时)
export const uploadService = axios.create({
  baseURL: '/api/v1',
  timeout: 300000,
})

// Token 刷新单飞模式 — 避免多个 401 同时触发多次刷新
let refreshPromise = null

async function doRefresh() {
  const refresh = localStorage.getItem('refresh_token')
  if (!refresh) throw new Error('no refresh token')
  const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token: refresh })
  localStorage.setItem('access_token', data.access_token)
  localStorage.setItem('refresh_token', data.refresh_token)
  return data.access_token
}

// 共享的 401 处理逻辑
async function handle401(error) {
  const refresh = localStorage.getItem('refresh_token')
  if (!refresh || error.config._retry) {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    router.push('/login')
    return Promise.reject(error)
  }
  error.config._retry = true
  try {
    // 单飞: 多个请求共享同一个刷新 Promise
    if (!refreshPromise) {
      refreshPromise = doRefresh().finally(() => { refreshPromise = null })
    }
    const newToken = await refreshPromise
    error.config.headers.Authorization = `Bearer ${newToken}`
    return service(error.config)
  } catch {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    router.push('/login')
    return Promise.reject(error)
  }
}

// 上传实例: 注入 token
uploadService.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
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
      return handle401(error)
    }

    ElMessage.error(detail)
    return Promise.reject(error)
  }
)

export default service
