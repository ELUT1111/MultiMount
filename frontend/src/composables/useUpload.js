/**
 * Upload composable with direct upload for small files and multipart upload for
 * larger files.
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  abortMultipartUpload,
  completeMultipartUpload,
  initMultipartUpload,
  uploadMultipartChunk,
} from '@/api/files'

const MULTIPART_THRESHOLD = 16 * 1024 * 1024
const DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024

function joinPath(base, child) {
  const cleanBase = (base || '/').replace(/\/+$/, '')
  const cleanChild = String(child || '').replace(/^\/+/, '')
  if (!cleanChild) return cleanBase || '/'
  if (!cleanBase || cleanBase === '/') return `/${cleanChild}`
  return `${cleanBase}/${cleanChild}`
}

function baseName(path) {
  return String(path || '').replace(/\\/g, '/').split('/').filter(Boolean).pop() || '未命名文件'
}

function parentPath(path) {
  const normalized = String(path || '').replace(/\\/g, '/').replace(/\/+$/, '')
  if (!normalized || normalized === '/') return '/'
  const index = normalized.lastIndexOf('/')
  return index > 0 ? normalized.slice(0, index) : '/'
}

export function useUpload() {
  const uploading = ref(false)
  const progress = ref(0)
  const currentFile = ref('')

  async function uploadDirect(mountId, dirPath, file, conflictPolicy, uploadName) {
    const formData = new FormData()
    formData.append('file', file, uploadName)

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const params = new URLSearchParams({
        path: dirPath,
        conflict_policy: conflictPolicy,
      })
      xhr.open('POST', `/api/v1/files/${mountId}/upload?${params.toString()}`)

      const token = localStorage.getItem('access_token')
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          progress.value = Math.round((e.loaded / e.total) * 100)
        }
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText))
        } else {
          reject(new Error(xhr.responseText || '上传失败'))
        }
      }

      xhr.onerror = () => reject(new Error('网络错误'))
      xhr.send(formData)
    })
  }

  async function uploadMultipart(mountId, dirPath, file, conflictPolicy, uploadName) {
    let uploadId = ''
    let uploadedBytes = 0
    const init = await initMultipartUpload(mountId, {
      filename: uploadName,
      path: dirPath,
      size: file.size,
      chunk_size: DEFAULT_CHUNK_SIZE,
      conflict_policy: conflictPolicy,
    })
    uploadId = init.upload_id
    const chunkSize = init.chunk_size || DEFAULT_CHUNK_SIZE
    const totalChunks = Math.ceil(file.size / chunkSize)

    try {
      for (let index = 0; index < totalChunks; index += 1) {
        const start = index * chunkSize
        const end = Math.min(start + chunkSize, file.size)
        const formData = new FormData()
        formData.append('chunk', file.slice(start, end), uploadName)

        await uploadMultipartChunk(mountId, uploadId, index, formData, (e) => {
          const chunkLoaded = e.lengthComputable ? e.loaded : 0
          progress.value = Math.min(
            99,
            Math.round(((uploadedBytes + chunkLoaded) / file.size) * 100),
          )
        })
        uploadedBytes += end - start
        progress.value = Math.min(99, Math.round((uploadedBytes / file.size) * 100))
      }

      const result = await completeMultipartUpload(mountId, uploadId)
      progress.value = 100
      return result
    } catch (err) {
      if (uploadId) {
        await abortMultipartUpload(mountId, uploadId).catch(() => {})
      }
      throw err
    }
  }

  /**
   * Upload a single file to the selected mount and directory.
   */
  async function upload(mountId, dirPath, file, options = {}) {
    uploading.value = true
    progress.value = 0
    const targetPath = options.targetPath || null
    const targetDirPath = options.targetDirPath || (targetPath ? parentPath(targetPath) : dirPath)
    const uploadName = baseName(options.filename || (targetPath ? baseName(targetPath) : file.name))
    const displayName = options.displayName || file.name
    currentFile.value = displayName
    const conflictPolicy = options.conflictPolicy || 'error'
    const silent = options.silent || false

    try {
      const result = file.size >= MULTIPART_THRESHOLD
        ? await uploadMultipart(mountId, targetDirPath, file, conflictPolicy, uploadName)
        : await uploadDirect(mountId, targetDirPath, file, conflictPolicy, uploadName)

      if (!silent) {
        ElMessage.success(`上传成功: ${displayName}`)
      }
      return result
    } catch (err) {
      if (!silent) {
        ElMessage.error(`上传失败: ${err.message}`)
      }
      throw err
    } finally {
      uploading.value = false
      progress.value = 0
      currentFile.value = ''
    }
  }

  async function uploadMultiple(mountId, dirPath, files, options = {}) {
    for (const file of files) {
      await upload(mountId, dirPath, file, options)
    }
  }

  return { uploading, progress, currentFile, upload, uploadMultiple }
}
