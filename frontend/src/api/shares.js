/**
 * 分享链接 API — 创建、查询、访问、删除分享链接。
 */
import request from '@/utils/request'

/** 创建分享链接 */
export const createShare = (data) => request.post('/shares', data)

/** 获取当前用户的分享链接列表 */
export const listMyShares = () => request.get('/shares')

/** 管理员: 获取所有分享链接 */
export const listAllShares = () => request.get('/shares/all')

/** 管理员: 获取分享安全策略 */
export const getSharePolicy = () => request.get('/shares/policy')

/** 管理员: 更新分享安全策略 */
export const updateSharePolicy = (data) => request.put('/shares/policy', data)

/** 批量管理分享链接 */
export const batchShare = (data) => request.post('/shares/batch', data)

/** 获取分享链接信息 (无需登录) */
export const getShareInfo = (token) => request.get(`/shares/${token}/info`, { suppressErrorMessage: true })

/** 浏览目录分享 */
export const listShareDir = (token, path = '/', accessCode = '') =>
  request.get(`/shares/${token}/list`, { params: { path, access_code: accessCode }, suppressErrorMessage: true })

/** 验证并访问分享链接 */
export const accessShare = (token, accessCode = '') =>
  request.post(`/shares/${token}/access`, { access_code: accessCode }, { suppressErrorMessage: true })

/** 通过分享链接下载文件 */
export const downloadShare = (token, accessCode = '') =>
  request.get(`/shares/${token}/download`, {
    params: { access_code: accessCode },
    responseType: 'blob',
    suppressErrorMessage: true,
  })

/** 删除分享链接 */
export const deleteShare = (linkId) => request.delete(`/shares/${linkId}`)

/** 编辑分享链接 */
export const updateShare = (linkId, data) => request.put(`/shares/${linkId}`, data)

/** 分享访问统计 */
export const getShareStats = (linkId) => request.get(`/shares/${linkId}/stats`)

/** 停用分享链接 (管理员) */
export const deactivateShare = (linkId) => request.post(`/shares/${linkId}/deactivate`)
