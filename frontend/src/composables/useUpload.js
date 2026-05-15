/**
 * 上传组合式函数 — 封装文件上传逻辑, 支持拖拽上传和进度追踪。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadFile as uploadFileApi } from '@/api/files'

export function useUpload() {
  const uploading = ref(false)
  const progress = ref(0)
  const currentFile = ref('')

  /**
   * 上传单个文件到指定挂载点的目标目录
   * @param {number} mountId - 挂载点 ID
   * @param {string} dirPath - 目标目录路径
   * @param {File} file - 浏览器 File 对象
   * @returns {Promise<object>} 上传后的文件信息
   */
  async function upload(mountId, dirPath, file) {
    uploading.value = true
    progress.value = 0
    currentFile.value = file.name

    try {
      // 构造 FormData
      const formData = new FormData()
      formData.append('file', file)

      // 使用 XMLHttpRequest 获取上传进度 (axios 对 upload progress 支持有限)
      const result = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', `/api/v1/files/${mountId}/upload?path=${encodeURIComponent(dirPath)}`)

        const token = localStorage.getItem('access_token')
        if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)

        // 上传进度回调
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

      ElMessage.success(`上传成功: ${file.name}`)
      return result
    } catch (err) {
      ElMessage.error(`上传失败: ${err.message}`)
      throw err
    } finally {
      uploading.value = false
      progress.value = 0
      currentFile.value = ''
    }
  }

  /**
   * 批量上传多个文件
   * @param {number} mountId - 挂载点 ID
   * @param {string} dirPath - 目标目录路径
   * @param {FileList} files - 浏览器 FileList
   */
  async function uploadMultiple(mountId, dirPath, files) {
    for (const file of files) {
      await upload(mountId, dirPath, file)
    }
  }

  return { uploading, progress, currentFile, upload, uploadMultiple }
}
