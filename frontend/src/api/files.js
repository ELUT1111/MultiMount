/**
 * 文件操作 API — 目录列表、文件上传/下载、CRUD 操作。
 */
import request, { uploadService } from '@/utils/request'

/** 列出目录内容 */
export const listFiles = (mountId, path = '/') =>
  request.get(`/files/${mountId}/list`, { params: { path } })

/** 获取文件元数据 */
export const getFileInfo = (mountId, path) =>
  request.get(`/files/${mountId}/info`, { params: { path } })

/** 下载文件 (返回 blob) */
export const downloadFile = (mountId, path) =>
  request.get(`/files/${mountId}/download`, { params: { path }, responseType: 'blob' })

/** 上传文件 (FormData) */
export const uploadFile = (mountId, path, formData, conflictPolicy = 'error') =>
  uploadService.post(`/files/${mountId}/upload`, formData, {
    params: { path, conflict_policy: conflictPolicy },
    headers: { 'Content-Type': 'multipart/form-data' },
  })

/** 初始化分片上传 */
export const initMultipartUpload = (mountId, data) =>
  request.post(`/files/${mountId}/multipart/init`, data)

/** 上传单个分片 */
export const uploadMultipartChunk = (mountId, uploadId, index, formData, onUploadProgress) =>
  uploadService.post(`/files/${mountId}/multipart/${uploadId}/chunk/${index}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
  })

/** 完成分片上传 */
export const completeMultipartUpload = (mountId, uploadId) =>
  request.post(`/files/${mountId}/multipart/${uploadId}/complete`)

/** 取消分片上传 */
export const abortMultipartUpload = (mountId, uploadId) =>
  request.delete(`/files/${mountId}/multipart/${uploadId}`)

/** 删除文件/目录 */
export const deleteFile = (mountId, path) =>
  request.delete(`/files/${mountId}/delete`, { params: { path } })

/** 创建目录 */
export const createDirectory = (mountId, path) =>
  request.post(`/files/${mountId}/mkdir`, null, { params: { path } })

/** 移动/重命名 */
export const moveFile = (mountId, src, dst, conflictPolicy = 'error') =>
  request.post(`/files/${mountId}/move`, { src, dst, conflict_policy: conflictPolicy })

/** 复制 */
export const copyFile = (mountId, src, dst, conflictPolicy = 'error') =>
  request.post(`/files/${mountId}/copy`, { src, dst, conflict_policy: conflictPolicy })

/** 生成分享链接 (委托给 shares API) */
export const createShareLink = (mountId, path) =>
  request.post('/shares', { mount_id: mountId, file_path: path })
