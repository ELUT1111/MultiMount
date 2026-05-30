<!--
  File preview dialog with large-text chunk loading, media preview, PDF embed,
  Markdown rendering, and graceful Office fallback.
-->
<template>
  <el-dialog v-model="visible" :title="fileName" class="responsive-dialog preview-dialog" destroy-on-close @close="cleanup">
    <div v-loading="loading" class="preview-container">
      <img v-if="kind === 'image' && previewUrl" :src="previewUrl" class="preview-image" @error="loadFailed = true" />

      <iframe v-else-if="kind === 'pdf' && previewUrl" :src="previewUrl" class="preview-frame" title="PDF preview" />

      <video v-else-if="kind === 'video' && previewUrl" class="preview-media" controls :src="previewUrl" />

      <audio v-else-if="kind === 'audio' && previewUrl" class="preview-audio" controls :src="previewUrl" />

      <iframe v-else-if="kind === 'office' && previewUrl && !loadFailed" :src="previewUrl" class="preview-frame" title="Office preview" @error="loadFailed = true" />

      <article v-else-if="isMarkdown" class="preview-markdown" v-html="markdownHtml" />

      <div v-else-if="isTextLike" class="text-preview-shell">
        <div class="text-toolbar">
          <span>{{ textMeta.language || 'text' }} / {{ textMeta.encoding || '-' }}</span>
          <el-button size="small" :disabled="!textMeta.next_offset || loadingMore" @click="loadMoreText">
            加载更多
          </el-button>
        </div>
        <pre class="preview-text">{{ textContent }}</pre>
      </div>

      <div v-else-if="kind === 'office'" class="preview-unsupported">
        <el-icon :size="48" color="#909399"><Document /></el-icon>
        <p>当前浏览器无法内嵌渲染此 Office 文档</p>
        <el-button type="primary" @click="$emit('download')">下载文件</el-button>
      </div>

      <div v-else class="preview-unsupported">
        <el-icon :size="48" color="#909399"><Document /></el-icon>
        <p>{{ loadFailed ? '预览加载失败' : '该文件类型不支持预览' }}</p>
        <el-button type="primary" @click="$emit('download')">下载文件</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Document } from '@element-plus/icons-vue'
import { getPreviewMeta, getTextPreview } from '@/api/files'

const props = defineProps({
  mountId: { type: Number, default: null },
  file: { type: Object, default: null },
})

defineEmits(['download'])

const visible = defineModel({ type: Boolean, default: false })
const meta = ref(null)
const textContent = ref('')
const textMeta = ref({})
const loadFailed = ref(false)
const loading = ref(false)
const loadingMore = ref(false)
const previewUrl = ref('')

const fileName = computed(() => props.file?.name || '预览')
const kind = computed(() => meta.value?.kind || inferKind(props.file))
const isMarkdown = computed(() => {
  const name = props.file?.name?.toLowerCase() || ''
  return kind.value === 'text' && (name.endsWith('.md') || name.endsWith('.markdown'))
})
const isTextLike = computed(() => kind.value === 'text' && !isMarkdown.value)
const markdownHtml = computed(() => renderMarkdown(textContent.value))

function inferKind(file) {
  if (!file || file.is_dir) return 'other'
  const mime = file.mime_type || ''
  const name = (file.name || '').toLowerCase()
  if (mime.startsWith('image/')) return 'image'
  if (mime.startsWith('video/')) return 'video'
  if (mime.startsWith('audio/')) return 'audio'
  if (mime === 'application/pdf' || name.endsWith('.pdf')) return 'pdf'
  if (mime.startsWith('text/') || ['.md', '.json', '.xml', '.log', '.csv'].some((ext) => name.endsWith(ext))) return 'text'
  if (['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'].some((ext) => name.endsWith(ext))) return 'office'
  return 'other'
}

function cleanup() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
  textContent.value = ''
  textMeta.value = {}
  meta.value = null
  loadFailed.value = false
  loading.value = false
  loadingMore.value = false
}

function getAuthHeaders() {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function getDownloadUrl() {
  return `/api/v1/files/${props.mountId}/download?path=${encodeURIComponent(props.file.path)}`
}

async function loadBlobPreview() {
  const resp = await fetch(getDownloadUrl(), { headers: getAuthHeaders() })
  if (!resp.ok) throw new Error('preview download failed')
  const blob = await resp.blob()
  previewUrl.value = URL.createObjectURL(blob)
}

async function loadText(offset = 0) {
  const data = await getTextPreview(props.mountId, props.file.path, offset, 65536)
  textMeta.value = data
  textContent.value += data.content || ''
}

async function loadMoreText() {
  if (!textMeta.value.next_offset) return
  loadingMore.value = true
  try {
    await loadText(textMeta.value.next_offset)
  } finally {
    loadingMore.value = false
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderMarkdown(markdown) {
  const escaped = escapeHtml(markdown)
  return escaped
    .replace(/^### (.*)$/gm, '<h3>$1</h3>')
    .replace(/^## (.*)$/gm, '<h2>$1</h2>')
    .replace(/^# (.*)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

watch(visible, async (val) => {
  if (!val || !props.file || !props.mountId) return
  cleanup()
  loading.value = true
  try {
    meta.value = await getPreviewMeta(props.mountId, props.file.path)
    if (['image', 'pdf', 'video', 'audio', 'office'].includes(kind.value)) {
      await loadBlobPreview()
    } else if (isTextLike.value || isMarkdown.value) {
      await loadText(0)
    }
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.preview-container {
  display: flex;
  justify-content: center;
  align-items: stretch;
  min-height: 360px;
  max-height: 74vh;
  overflow: auto;
}
.preview-image { max-width: 100%; max-height: 74vh; object-fit: contain; margin: auto; }
.preview-frame {
  width: 100%;
  min-height: 70vh;
  border: 0;
  border-radius: 6px;
  background: color-mix(in srgb, var(--border-color) 35%, transparent);
}
.preview-media { width: 100%; max-height: 70vh; background: #111; border-radius: 6px; }
.preview-audio { width: min(640px, 100%); margin: auto; }
.text-preview-shell { width: 100%; display: flex; flex-direction: column; gap: 8px; }
.text-toolbar { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--text-secondary); }
.preview-text {
  width: 100%;
  max-height: 68vh;
  overflow: auto;
  padding: 16px;
  color: var(--text-regular);
  background: color-mix(in srgb, var(--border-color) 30%, transparent);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 13px;
  font-family: Consolas, Monaco, monospace;
  white-space: pre-wrap;
  word-break: break-word;
}
.preview-markdown {
  width: 100%;
  max-height: 70vh;
  overflow: auto;
  padding: 18px;
  line-height: 1.7;
}
.preview-markdown :deep(code) {
  padding: 2px 5px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--border-color) 36%, transparent);
  font-family: Consolas, Monaco, monospace;
}
.preview-unsupported { width: 100%; text-align: center; color: var(--text-secondary); align-self: center; }
.preview-unsupported p { margin: 12px 0; }
</style>
