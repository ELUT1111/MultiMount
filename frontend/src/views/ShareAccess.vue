<template>
  <main class="share-page">
    <section class="share-panel">
      <div class="share-brand">
        <el-icon :size="28"><Link /></el-icon>
        <span>MultiMount 分享</span>
      </div>

      <div v-if="loading" v-loading="true" class="share-loading" />

      <template v-else-if="error">
        <el-result icon="error" title="分享不可用" :sub-title="error">
          <template #extra>
            <el-button @click="loadInfo">重试</el-button>
          </template>
        </el-result>
      </template>

      <template v-else>
        <div class="share-file">
          <el-icon :size="34"><Document /></el-icon>
          <div>
            <h1>{{ fileName }}</h1>
            <p>{{ info.file_path }}</p>
          </div>
        </div>

        <div class="share-meta">
          <span>访问 {{ info.view_count }} 次</span>
          <span v-if="info.max_views">最多 {{ info.max_views }} 次</span>
          <span v-if="info.expires_at">有效期至 {{ formatTime(info.expires_at) }}</span>
        </div>

        <el-form class="share-form" @submit.prevent>
          <el-form-item v-if="info.has_access_code" label="提取码">
            <el-input v-model="accessCode" placeholder="请输入提取码" show-password @keyup.enter="handleAccess" />
          </el-form-item>
          <el-button type="primary" :loading="accessing" @click="handleAccess">
            {{ verified ? '重新下载' : '下载文件' }}
          </el-button>
        </el-form>
      </template>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Document, Link } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { downloadShare, getShareInfo } from '@/api/shares'

const route = useRoute()
const token = computed(() => route.params.token)
const loading = ref(false)
const accessing = ref(false)
const error = ref('')
const info = ref({})
const accessCode = ref('')
const verified = ref(false)

const fileName = computed(() => {
  const path = info.value.file_path || ''
  return path.split('/').filter(Boolean).pop() || '分享文件'
})

function formatTime(iso) {
  return new Date(iso).toLocaleString('zh-CN')
}

async function loadInfo() {
  loading.value = true
  error.value = ''
  try {
    info.value = await getShareInfo(token.value)
  } catch (e) {
    error.value = e.response?.data?.detail || '分享链接不存在或已失效'
  } finally {
    loading.value = false
  }
}

async function handleAccess() {
  accessing.value = true
  try {
    const blob = await downloadShare(token.value, accessCode.value)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName.value
    a.click()
    URL.revokeObjectURL(url)
    verified.value = true
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '访问失败')
  } finally {
    accessing.value = false
  }
}

onMounted(loadInfo)
</script>

<style scoped>
.share-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: var(--bg-color);
}
.share-panel {
  width: min(560px, 100%);
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
}
.share-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--primary-color);
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 22px;
}
.share-loading { height: 180px; }
.share-file {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.share-file h1 {
  margin: 0 0 6px;
  font-size: 20px;
  word-break: break-word;
}
.share-file p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  word-break: break-all;
}
.share-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  color: var(--text-secondary);
  font-size: 13px;
  margin-bottom: 18px;
}
.share-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
