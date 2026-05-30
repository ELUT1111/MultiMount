<template>
  <main class="share-page">
    <section class="share-shell">
      <div class="share-hero">
        <div class="brand-row">
          <span class="brand-mark"><el-icon><Link /></el-icon></span>
          <span>MultiMount 分享</span>
        </div>
        <div class="hero-copy">
          <p>Secure Delivery</p>
          <h1>安全接收共享内容</h1>
          <span>通过受控分享链接访问文件、目录和下载包。</span>
        </div>
        <div class="hero-orbit" aria-hidden="true">
          <span class="orbit-node node-a" />
          <span class="orbit-node node-b" />
          <span class="orbit-node node-c" />
        </div>
      </div>

      <div v-if="loading" v-loading="true" class="share-loading" />

      <template v-else-if="error">
        <el-result class="share-result" icon="error" title="分享不可用" :sub-title="error">
          <template #extra>
            <el-button @click="loadInfo">重试</el-button>
          </template>
        </el-result>
      </template>

      <template v-else>
        <section class="delivery-card">
          <div class="file-summary">
            <div class="file-icon" :class="{ directory: info.is_dir }">
              <el-icon :size="30"><Folder v-if="info.is_dir" /><Document v-else /></el-icon>
            </div>
            <div class="file-copy">
              <span class="file-kind">{{ fileKind }}</span>
              <h2>{{ fileName }}</h2>
              <p>{{ info.file_path }}</p>
            </div>
          </div>

          <div class="share-meta">
            <span>
              <strong>{{ info.view_count || 0 }}</strong>
              已访问
            </span>
            <span>
              <strong>{{ info.max_views || '不限' }}</strong>
              访问上限
            </span>
            <span>
              <strong>{{ expiresText }}</strong>
              有效期
            </span>
          </div>

          <el-form class="share-form" @submit.prevent>
            <div v-if="info.has_access_code" class="access-box">
              <div class="access-copy">
                <el-icon><Lock /></el-icon>
                <div>
                  <strong>需要提取码</strong>
                  <span>输入提取码后即可访问分享内容</span>
                </div>
              </div>
              <el-form-item label="提取码">
                <el-input v-model="accessCode" placeholder="请输入提取码" show-password @keyup.enter="handleAccess" />
              </el-form-item>
            </div>

            <div v-if="info.is_dir" class="dir-browser">
              <div class="dir-toolbar">
                <div>
                  <strong>目录预览</strong>
                  <span>{{ dirPath }}</span>
                </div>
                <el-button size="small" :disabled="dirPath === '/'" @click="goUp">上级</el-button>
              </div>
              <div v-if="!verified" class="dir-locked">
                <el-icon><Lock /></el-icon>
                <span>{{ info.has_access_code ? '输入提取码后可浏览目录' : '点击下载按钮后可加载目录内容' }}</span>
              </div>
              <div v-else v-loading="dirLoading" class="dir-list">
                <button v-for="item in dirItems" :key="item.path" class="dir-item" :class="{ clickable: item.is_dir }" @click="item.is_dir ? openDir(item) : null">
                  <span class="dir-item-icon">
                    <el-icon><Folder v-if="item.is_dir" /><Document v-else /></el-icon>
                  </span>
                  <span class="dir-item-name">{{ item.name }}</span>
                  <small>{{ item.is_dir ? '目录' : formatSize(item.size) }}</small>
                </button>
                <el-empty v-if="!dirLoading && !dirItems.length" description="目录为空" :image-size="48" />
              </div>
            </div>

            <el-button class="download-button" type="primary" :icon="Download" :loading="accessing" @click="handleAccess">
              {{ info.is_dir ? '下载目录 ZIP' : (verified ? '重新下载' : '下载文件') }}
            </el-button>
          </el-form>
        </section>
      </template>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Document, Download, Folder, Link, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { downloadShare, getShareInfo, listShareDir } from '@/api/shares'
import { formatSize } from '@/utils/format'

const route = useRoute()
const token = computed(() => route.params.token)
const loading = ref(false)
const accessing = ref(false)
const error = ref('')
const info = ref({})
const accessCode = ref('')
const verified = ref(false)
const dirLoading = ref(false)
const dirPath = ref('/')
const dirItems = ref([])

const fileName = computed(() => {
  const path = info.value.file_path || ''
  return path.split('/').filter(Boolean).pop() || '分享文件'
})

const downloadName = computed(() => info.value.is_dir ? `${fileName.value}.zip` : fileName.value)
const fileKind = computed(() => info.value.is_dir ? '目录分享' : '文件分享')
const expiresText = computed(() => info.value.expires_at ? formatTime(info.value.expires_at) : '长期有效')

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

async function errorMessage(error, fallback) {
  const data = error.response?.data
  if (data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text())
      return parsed.detail || fallback
    } catch {
      return fallback
    }
  }
  return data?.detail || fallback
}

async function handleAccess() {
  accessing.value = true
  try {
    if (info.value.is_dir && !verified.value) {
      await loadDir('/')
      verified.value = true
    }
    const blob = await downloadShare(token.value, accessCode.value)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = downloadName.value
    a.click()
    URL.revokeObjectURL(url)
    verified.value = true
  } catch (e) {
    ElMessage.error(await errorMessage(e, '访问失败'))
  } finally {
    accessing.value = false
  }
}

async function loadDir(path = '/') {
  dirLoading.value = true
  try {
    dirItems.value = await listShareDir(token.value, path, accessCode.value)
    dirPath.value = path
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '目录加载失败')
  } finally {
    dirLoading.value = false
  }
}

function openDir(item) {
  const next = item.path === '/' ? '/' : '/' + item.path.replace(/^\/+/, '')
  loadDir(next)
}

function goUp() {
  const parts = dirPath.value.split('/').filter(Boolean)
  parts.pop()
  loadDir(parts.length ? '/' + parts.join('/') : '/')
}

onMounted(loadInfo)
</script>

<style scoped>
.share-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background:
    radial-gradient(circle at 12% 18%, rgba(64,158,255,0.18), transparent 30%),
    radial-gradient(circle at 84% 12%, rgba(103,194,58,0.14), transparent 28%),
    linear-gradient(135deg, #f3f8ff 0%, #f8fbff 54%, #f1fbf5 100%);
}

.share-shell {
  width: min(980px, 100%);
  min-height: 620px;
  display: grid;
  grid-template-columns: minmax(300px, 0.82fr) minmax(360px, 1fr);
  overflow: hidden;
  border: 1px solid rgba(148,163,184,0.24);
  border-radius: 22px;
  background: rgba(255,255,255,0.78);
  box-shadow: 0 24px 72px rgba(15,23,42,0.16);
  backdrop-filter: blur(18px);
}

.share-hero {
  position: relative;
  overflow: hidden;
  padding: 34px;
  color: #fff;
  background:
    linear-gradient(145deg, rgba(15,76,129,0.96), rgba(15,118,110,0.94)),
    #12385f;
}

.share-hero::before {
  content: "";
  position: absolute;
  inset: 0;
  opacity: 0.24;
  background-image:
    linear-gradient(rgba(255,255,255,0.16) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.16) 1px, transparent 1px);
  background-size: 38px 38px;
  mask-image: radial-gradient(circle at center, black 0%, transparent 75%);
}

.brand-row {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 800;
}

.brand-mark {
  width: 42px;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: rgba(255,255,255,0.16);
  border: 1px solid rgba(255,255,255,0.26);
}

.hero-copy {
  position: relative;
  z-index: 2;
  margin-top: 150px;
}

.hero-copy p {
  margin: 0 0 10px;
  color: rgba(255,255,255,0.68);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-copy h1 {
  margin: 0;
  font-size: 34px;
  line-height: 1.16;
  letter-spacing: 0;
}

.hero-copy span {
  display: block;
  margin-top: 12px;
  max-width: 280px;
  color: rgba(255,255,255,0.72);
  font-size: 14px;
  line-height: 1.7;
}

.hero-orbit {
  position: absolute;
  inset: 88px 34px auto auto;
  width: 190px;
  height: 190px;
  border: 1px solid rgba(255,255,255,0.22);
  border-radius: 50%;
  animation: orbit-spin 22s linear infinite;
}

.hero-orbit::before {
  content: "";
  position: absolute;
  inset: 38px;
  border: 1px dashed rgba(255,255,255,0.24);
  border-radius: 50%;
}

.orbit-node {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #86efac;
  box-shadow: 0 0 18px rgba(134,239,172,0.8);
}

.node-a { left: 22px; top: 34px; }
.node-b { right: 28px; top: 62px; background: #7dd3fc; }
.node-c { left: 86px; bottom: 10px; background: #fef08a; }

.delivery-card,
.share-loading,
.share-result {
  margin: 34px;
}

.delivery-card {
  align-self: center;
}

.share-loading { min-height: 320px; }

.file-summary {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.file-icon {
  width: 58px;
  height: 58px;
  flex: 0 0 58px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  color: var(--primary-color);
  background: rgba(64,158,255,0.1);
  border: 1px solid rgba(64,158,255,0.18);
}

.file-icon.directory {
  color: var(--success-color);
  background: rgba(103,194,58,0.1);
  border-color: rgba(103,194,58,0.2);
}

.file-copy {
  min-width: 0;
}

.file-kind {
  display: inline-block;
  margin-bottom: 6px;
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 800;
}

.file-copy h2 {
  margin: 0 0 6px;
  color: var(--text-primary);
  font-size: 24px;
  line-height: 1.25;
  word-break: break-word;
}

.file-copy p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  word-break: break-all;
}

.share-meta {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin: 18px 0 22px;
}

.share-meta span {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: rgba(248,250,252,0.72);
  color: var(--text-secondary);
  font-size: 12px;
}

.share-meta strong {
  display: block;
  overflow: hidden;
  margin-bottom: 4px;
  color: var(--text-primary);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.share-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.access-box {
  padding: 14px;
  border: 1px solid rgba(64,158,255,0.18);
  border-radius: 14px;
  background: rgba(64,158,255,0.06);
}

.access-copy {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  color: var(--text-primary);
}

.access-copy > .el-icon {
  color: var(--primary-color);
}

.access-copy div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.access-copy span {
  color: var(--text-secondary);
  font-size: 12px;
}

.access-box :deep(.el-form-item) {
  margin-bottom: 0;
}

.dir-browser {
  border: 1px solid var(--border-color);
  border-radius: 14px;
  overflow: hidden;
  background: var(--card-bg);
}

.dir-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  background: rgba(64,158,255,0.06);
}

.dir-toolbar div {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.dir-toolbar strong {
  color: var(--text-primary);
  font-size: 13px;
}

.dir-toolbar span {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dir-locked {
  min-height: 112px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}

.dir-locked .el-icon {
  color: var(--primary-color);
}

.dir-list {
  min-height: 120px;
  max-height: 260px;
  overflow: auto;
}

.dir-item {
  width: 100%;
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 0;
  border-bottom: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-primary);
  text-align: left;
  cursor: default;
}

.dir-item.clickable {
  cursor: pointer;
}

.dir-item.clickable:hover {
  background: rgba(64,158,255,0.06);
}

.dir-item-icon {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: var(--primary-color);
  background: rgba(64,158,255,0.08);
}

.dir-item-name {
  overflow: hidden;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dir-item small { color: var(--text-secondary); white-space: nowrap; }

.download-button {
  width: 100%;
  height: 48px;
  border: 0;
  border-radius: 12px;
  font-weight: 800;
  background: linear-gradient(135deg, #409eff 0%, #0f766e 100%);
  box-shadow: 0 14px 30px rgba(64,158,255,0.24);
}

@keyframes orbit-spin {
  to { transform: rotate(360deg); }
}

.dark .share-page {
  background:
    radial-gradient(circle at 12% 18%, rgba(64,158,255,0.12), transparent 30%),
    radial-gradient(circle at 84% 12%, rgba(103,194,58,0.1), transparent 28%),
    linear-gradient(135deg, #07111f 0%, #0f172a 100%);
}

.dark .share-shell {
  background: rgba(15,23,42,0.74);
  border-color: rgba(148,163,184,0.18);
}

.dark .share-meta span {
  background: rgba(30,41,59,0.62);
}

@media (max-width: 820px) {
  .share-page {
    align-items: stretch;
    padding: 16px;
  }

  .share-shell {
    grid-template-columns: 1fr;
    min-height: auto;
    border-radius: 18px;
  }

  .share-hero {
    padding: 22px;
  }

  .hero-copy {
    margin-top: 54px;
  }

  .hero-copy h1 {
    font-size: 28px;
  }

  .hero-orbit {
    width: 132px;
    height: 132px;
    inset: 54px 18px auto auto;
  }

  .delivery-card,
  .share-loading,
  .share-result {
    margin: 22px;
  }

  .share-meta {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-orbit {
    animation: none;
  }
}
</style>
