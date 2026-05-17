import request from '@/utils/request'

/**
 * 跨挂载点搜索文件
 * @param {object} params - { q, regex, mount_id, max_depth, limit }
 */
export const searchFiles = (params) => request.get('/search', { params })
