<!--
  文件预览组件 — 支持图片和文本文件的内联预览, 在对话框中展示。
-->
<template>
  <el-dialog v-model="visible" :title="fileName" width="70%" destroy-on-close>
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

const fileName = computed(() => props.file?.name || '预览')
const isImage = computed(() => {
  const mime = props.file?.mime_type || ''
  return mime.startsWith('image/') && !loadFailed.value
})
const isText = computed(() => {
  const mime = props.file?.mime_type || ''
  return mime.startsWith('text/') || ['application/json', 'application/xml'].includes(mime)
})
const previewUrl = computed(() => {
  if (!props.file || !props.mountId) return ''
  const token = localStorage.getItem('access_token')
  return `/api/v1/files/${props.mountId}/download?path=${encodeURIComponent(props.file.path)}&token=${token}`
})

// 文本文件: 打开时加载内容
watch(visible, async (val) => {
  if (val && isText.value && props.file) {
    try {
      const token = localStorage.getItem('access_token')
      const resp = await fetch(`/api/v1/files/${props.mountId}/download?path=${encodeURIComponent(props.file.path)}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      textContent.value = await resp.text()
    } catch {
      textContent.value = '加载失败'
    }
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
