/**
 * 文件操作 API — 目录列表、文件上传/下载、CRUD 操作。
 */
import request from '@/utils/request'

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
export const uploadFile = (mountId, path, formData) =>
  request.post(`/files/${mountId}/upload`, formData, {
    params: { path },
    headers: { 'Content-Type': 'multipart/form-data' },
  })

/** 删除文件/目录 */
export const deleteFile = (mountId, path) =>
  request.delete(`/files/${mountId}/delete`, { params: { path } })

/** 创建目录 */
export const createDirectory = (mountId, path) =>
  request.post(`/files/${mountId}/mkdir`, null, { params: { path } })

/** 移动/重命名 */
export const moveFile = (mountId, src, dst) =>
  request.post(`/files/${mountId}/move`, { src, dst })

/** 复制 */
export const copyFile = (mountId, src, dst) =>
  request.post(`/files/${mountId}/copy`, { src, dst })

/** 生成分享链接 */
export const createShareLink = (mountId, path) =>
  request.post(`/files/${mountId}/share`, { path })
