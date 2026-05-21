import request from '@/utils/request'

/**
 * 跨挂载点搜索文件
 * @param {object} params - { q, regex, mount_id, max_depth, limit, size_min, size_max, modified_from, modified_to, file_type, extension, path_prefix, owner }
 */
export const searchFiles = (params) => request.get('/search', { params })

/** 刷新文件搜索索引 */
export const refreshSearchIndex = (params) => request.post('/search/index/refresh', null, { params })
