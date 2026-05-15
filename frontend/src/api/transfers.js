/**
 * 传输任务 API — 任务 CRUD、暂停/恢复/取消/重试。
 */
import request from '@/utils/request'

/** 查询传输任务列表 */
export const listTransfers = (params) => request.get('/transfers', { params })

/** 获取单个任务详情 */
export const getTransfer = (id) => request.get(`/transfers/${id}`)

/** 创建传输任务 */
export const createTransfer = (data) => request.post('/transfers', data)

/** 暂停任务 */
export const pauseTransfer = (id) => request.post(`/transfers/${id}/pause`)

/** 恢复任务 (断点续传) */
export const resumeTransfer = (id) => request.post(`/transfers/${id}/resume`)

/** 取消/删除任务 */
export const cancelTransfer = (id) => request.delete(`/transfers/${id}`)

/** 重试失败的任务 */
export const retryTransfer = (id) => request.post(`/transfers/${id}/retry`)
