/**
 * WebDAV 服务管理 API — 状态查询、启停、配置更新。
 */
import request from '@/utils/request'

/** 获取 WebDAV 服务状态 */
export const getWebDAVStatus = () => request.get('/webdav/status')

/** 启动 WebDAV 服务 */
export const startWebDAV = (config) => request.post('/webdav/start', config)

/** 停止 WebDAV 服务 */
export const stopWebDAV = () => request.post('/webdav/stop')

/** 更新 WebDAV 配置 (热更新) */
export const updateWebDAVConfig = (config) => request.put('/webdav/config', config)
