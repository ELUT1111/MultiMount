/**
 * 系统设置 API — HTTPS 配置、日志管理、系统信息、访问监控、IP 黑名单。
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

// ── 访问监控 & IP 黑名单 ──────────────────────────────────

/** 分页获取访问日志 */
export const getAccessLogs = (params) => request.get('/system/access-logs', { params })

/** 获取访问统计摘要 */
export const getAccessStats = () => request.get('/system/access-stats')

/** 分页获取业务操作审计日志 */
export const getOperationLogs = (params) => request.get('/system/operation-logs', { params })

/** 获取 IP 黑名单列表 */
export const getIPBlacklist = () => request.get('/system/ip-blacklist')

/** 添加 IP 到黑名单 */
export const addIPBlacklist = (data) => request.post('/system/ip-blacklist', data)

/** 从黑名单移除 IP */
export const removeIPBlacklist = (ip) => request.delete(`/system/ip-blacklist/${encodeURIComponent(ip)}`)
