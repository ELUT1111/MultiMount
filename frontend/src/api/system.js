/**
 * 系统设置 API — HTTPS 配置、日志管理、系统信息。
 */
import request from '@/utils/request'

/** 获取系统信息 */
export const getSystemInfo = () => request.get('/system/info')

/** 获取 HTTPS 配置状态 */
export const getHttpsStatus = () => request.get('/system/https')

/** 上传 SSL 证书 */
export const uploadCert = (file) => {
  const fd = new FormData()
  fd.append('cert', file)
  return request.post('/system/https/cert', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}

/** 上传 SSL 私钥 */
export const uploadKey = (file) => {
  const fd = new FormData()
  fd.append('key', file)
  return request.post('/system/https/key', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}

/** 更新 HTTPS 配置 */
export const updateHttpsConfig = (config) => request.put('/system/https', config)

/** 获取日志列表 */
export const getLogs = (params) => request.get('/system/logs', { params })

/** 导出日志 */
export const exportLogs = (logType) => request.post('/system/logs/export', null, { params: { log_type: logType } })

/** 清空日志 */
export const clearLogs = (logType) => request.post('/system/logs/clear', null, { params: { log_type: logType } })

/** 浏览服务器本地目录 (仅返回文件夹) */
export const browseFolders = (path = '') => request.get('/system/browse', { params: { path } })
