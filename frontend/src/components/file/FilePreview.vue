<!--
  文件预览组件 — 支持图片和文本文件的内联预览, 在对话框中展示。
-->
<template>
  <el-dialog v-model="visible" :title="fileName" width="70%" destroy-on-close @close="cleanup">
    <div class="preview-container">
      <!-- 图片预览 -->
      <img v-if="isImage" :src="previewUrl" class="preview-image" @error="loadFailed = true" />
      <!-- 文本预览 -->
      <pre v-else-if="isText" class="preview-text">{{ textContent }}</pre>
      <!-- 不支持的类型 -->
      <div v-else class="preview-unsupported">
        <el-icon :size="48" color="#909399"><Document /></el-icon>
        <p>该文件类型不支持预览</p>
        <el-button type="primary" @click="$emit('download')">下载文件</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Document } from '@element-plus/icons-vue'

const props = defineProps({
  mountId: { type: Number, required: true },
  file: { type: Object, default: null },
})

defineEmits(['download'])

const visible = defineModel({ type: Boolean, default: false })
const textContent = ref('')
const loadFailed = ref(false)
const previewUrl = ref('')

const fileName = computed(() => props.file?.name || '预览')
const isImage = computed(() => {
  const mime = props.file?.mime_type || ''
  return mime.startsWith('image/') && !loadFailed.value
})
const isText = computed(() => {
  const mime = props.file?.mime_type || ''
  return mime.startsWith('text/') || ['application/json', 'application/xml'].includes(mime)
})

function cleanup() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
  textContent.value = ''
  loadFailed.value = false
}

function getDownloadUrl() {
  return `/api/v1/files/${props.mountId}/download?path=${encodeURIComponent(props.file.path)}`
}

function getAuthHeaders() {
  const token = localStorage.getItem('access_token')
  return { Authorization: `Bearer ${token}` }
}

// 图片: 通过 Authorization header 获取 blob, 创建 object URL (避免 token 泄露到 URL)
// 文本: 通过 fetch 获取内容
watch(visible, async (val) => {
  if (!val || !props.file) return
  cleanup()
  try {
    const resp = await fetch(getDownloadUrl(), { headers: getAuthHeaders() })
    if (!resp.ok) throw new Error('fetch failed')
    if (isImage.value) {
      const blob = await resp.blob()
      previewUrl.value = URL.createObjectURL(blob)
    } else if (isText.value) {
      textContent.value = await resp.text()
    }
  } catch {
    if (isImage.value) loadFailed.value = true
    else if (isText.value) textContent.value = '加载失败'
  }
})
</script>

<style scoped>
.preview-container {
  display: flex; justify-content: center; align-items: center;
  min-height: 300px; max-height: 70vh; overflow: auto;
}
.preview-image { max-width: 100%; max-height: 70vh; object-fit: contain; }
.preview-text {
  width: 100%; max-height: 70vh; overflow: auto; padding: 16px;
  background: #f5f7fa; border-radius: 8px; font-size: 13px;
  font-family: 'Consolas', 'Monaco', monospace; white-space: pre-wrap; word-break: break-all;
}
.preview-unsupported { text-align: center; color: var(--text-secondary); }
.preview-unsupported p { margin: 12px 0; }
</style>
