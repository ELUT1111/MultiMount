<!--
  系统设置页面 — 基本设置、HTTPS配置、WebDAV服务配置、日志管理。
  连接后端 API 实现配置持久化和日志查询。
-->
<template>
  <div class="system-settings">
    <h2>系统设置</h2>
    <el-tabs v-model="activeMenu" tab-position="left">
      <!-- 基本设置 -->
      <el-tab-pane label="基本设置" name="basic">
        <h3>基本设置</h3>
        <el-form label-width="120px" style="max-width: 500px; margin-top: 16px">
          <el-form-item label="应用名称"><el-input :value="systemInfo.app_name" disabled /></el-form-item>
          <el-form-item label="版本"><el-input :value="systemInfo.version" disabled /></el-form-item>
          <el-form-item label="运行平台"><el-input :value="systemInfo.platform" disabled /></el-form-item>
          <el-form-item label="Python 版本"><el-input :value="systemInfo.python_version?.split(' ')[0]" disabled /></el-form-item>
          <el-form-item label="深色模式">
            <el-switch :model-value="appPrefs.isDark" @change="(val) => appPrefs.setTheme(val ? 'dark' : 'light')" active-text="深色" inactive-text="浅色" />
          </el-form-item>
          <el-form-item label="高对比">
            <el-switch v-model="appPrefs.highContrast" @change="appPrefs.applyPreferences" active-text="开启" inactive-text="关闭" />
          </el-form-item>
          <el-form-item label="紧凑模式">
            <el-switch v-model="appPrefs.compactMode" @change="appPrefs.applyPreferences" active-text="开启" inactive-text="关闭" />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- HTTPS 配置 -->
      <el-tab-pane label="HTTPS 配置" name="https">
        <h3>HTTPS 配置</h3>
        <el-card style="margin-top: 16px; max-width: 600px">
          <div class="cert-status">
            <el-icon :size="20" :color="httpsConfig.cert_valid ? '#67c23a' : '#f56c6c'">
              <component :is="httpsConfig.cert_valid ? CircleCheckFilled : CircleCloseFilled" />
            </el-icon>
            <span>{{ httpsConfig.cert_valid ? '证书有效' : '证书未配置' }}</span>
            <span v-if="httpsConfig.cert_expiry" class="cert-expiry">有效期至: {{ httpsConfig.cert_expiry }}</span>
          </div>
          <el-alert
            v-if="httpsConfig.cert_expiry_warning"
            type="warning"
            show-icon
            :closable="false"
            class="inline-alert"
            :title="`证书将在 ${httpsConfig.cert_days_remaining ?? 0} 天内过期`"
          />
          <el-divider />
          <el-upload drag action="#" :auto-upload="false" accept=".crt,.pem" :on-change="handleCertUpload">
            <el-icon :size="40"><UploadFilled /></el-icon>
            <div>拖拽上传证书文件 (.crt/.pem)</div>
          </el-upload>
          <el-upload drag action="#" :auto-upload="false" accept=".key,.pem" style="margin-top: 12px" :on-change="handleKeyUpload">
            <el-icon :size="40"><UploadFilled /></el-icon>
            <div>拖拽上传私钥文件 (.key/.pem)</div>
          </el-upload>
          <el-divider />
          <div class="https-options">
            <el-switch v-model="httpsConfig.force_https" active-text="强制 HTTPS 跳转" @change="handleHttpsConfigChange" />
            <el-switch v-model="httpsConfig.auto_redirect" active-text="HTTP 自动重定向到 HTTPS" style="margin-top: 12px" @change="handleHttpsConfigChange" />
          </div>
          <el-divider />
          <el-collapse>
            <el-collapse-item title="反向代理配置" name="proxy">
              <div class="proxy-block">
                <div class="proxy-title">Nginx</div>
                <pre>{{ httpsConfig.reverse_proxy?.nginx?.join('\n') }}</pre>
                <div class="proxy-title">Caddy</div>
                <pre>{{ httpsConfig.reverse_proxy?.caddy?.join('\n') }}</pre>
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-card>
      </el-tab-pane>

      <!-- WebDAV 服务 -->
      <el-tab-pane label="WebDAV 服务" name="webdav">
        <h3>WebDAV 服务</h3>
        <el-card style="margin-top: 16px; max-width: 600px">
          <div class="webdav-status">
            <StatusBadge :status="webdavRunning ? 'online' : 'offline'" :label="'WebDAV 服务' + (webdavRunning ? '运行中' : '已停止')" />
            <el-switch v-model="webdavRunning" style="margin-left: auto" @change="handleWebdavToggle" />
          </div>
          <div class="service-url">
            <span>访问地址</span>
            <code>{{ webdavConfig.url }}</code>
          </div>
          <el-divider />
          <el-form label-width="120px" style="margin-top: 12px">
            <el-form-item label="监听地址"><el-input v-model="webdavConfig.host" placeholder="0.0.0.0" /></el-form-item>
            <el-form-item label="端口"><el-input-number v-model="webdavConfig.port" :min="1" :max="65535" /></el-form-item>
            <el-form-item label="SSL/TLS">
              <el-switch v-model="webdavConfig.ssl" active-text="启用" />
            </el-form-item>
            <el-form-item label="根目录">
              <el-select v-model="webdavConfig.root_mount" placeholder="选择挂载点作为根目录" clearable style="width: 100%">
                <el-option v-for="m in mounts.mounts" :key="m.id" :label="m.name" :value="m.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="访问日志">
              <el-switch v-model="webdavConfig.access_log" />
            </el-form-item>
            <el-form-item label="删除策略">
              <el-switch v-model="webdavConfig.recycle_delete" active-text="进入回收站" inactive-text="直接删除" />
            </el-form-item>
            <el-form-item label="日志路径" v-if="webdavConfig.access_log">
              <el-input v-model="webdavConfig.log_path" placeholder="/var/log/webdav/access.log" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSaveWebdav">保存配置</el-button>
            </el-form-item>
          </el-form>
          <el-divider />
          <div class="permission-map">
            <el-tag type="info">多根目录按当前登录用户动态展示</el-tag>
            <el-tag type="success">读操作复用下载/查看权限</el-tag>
            <el-tag type="warning">写操作复用上传/修改/删除权限</el-tag>
          </div>
          <el-divider />
          <el-tabs>
            <el-tab-pane label="Windows 连接指南">
              <ol class="guide-list">
                <li>打开资源管理器</li>
                <li>右键「此电脑」→ 映射网络驱动器</li>
                <li>输入 WebDAV 地址: <code>https://your-server:{{ webdavConfig.port }}</code></li>
                <li>输入账号密码完成连接</li>
              </ol>
            </el-tab-pane>
            <el-tab-pane label="macOS 连接指南">
              <ol class="guide-list">
                <li>打开 Finder</li>
                <li>菜单栏「前往」→「连接服务器」</li>
                <li>输入 WebDAV 地址: <code>https://your-server:{{ webdavConfig.port }}</code></li>
                <li>输入账号密码完成连接</li>
              </ol>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-tab-pane>

      <!-- 日志管理 -->
      <el-tab-pane label="日志管理" name="logs">
        <h3>日志管理</h3>
        <el-card style="margin-top: 16px">
          <div class="log-toolbar">
            <el-radio-group v-model="logType" size="default" @change="fetchLogs">
              <el-radio-button label="system">系统日志</el-radio-button>
              <el-radio-button label="access">访问日志</el-radio-button>
              <el-radio-button label="transfer">传输日志</el-radio-button>
            </el-radio-group>
            <div class="log-actions">
              <el-date-picker v-model="logDateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" size="default" style="width: 260px" @change="fetchLogs" />
              <el-button :icon="Download" @click="handleExportLog">导出</el-button>
              <el-button type="danger" plain @click="handleClearLog">清空</el-button>
            </div>
          </div>
          <el-table :data="logEntries" style="margin-top: 16px" max-height="400" v-loading="logLoading">
            <el-table-column prop="timestamp" label="时间" width="180" />
            <el-table-column prop="level" label="级别" width="80">
              <template #default="{ row }">
                <el-tag :type="logLevelType(row.level)" size="small">{{ row.level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="消息" show-overflow-tooltip />
            <el-table-column prop="source" label="来源" width="120" />
          </el-table>
          <el-empty v-if="!logLoading && logEntries.length === 0" description="暂无日志记录" />
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { CircleCheckFilled, CircleCloseFilled, UploadFilled, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMountsStore } from '@/stores/mounts'
import { useAppStore } from '@/stores/app'
import { getWebDAVStatus, startWebDAV, stopWebDAV, updateWebDAVConfig } from '@/api/webdav'
import { getSystemInfo, getHttpsStatus, uploadCert, uploadKey, updateHttpsConfig, getLogs, exportLogs, clearLogs } from '@/api/system'
import StatusBadge from '@/components/common/StatusBadge.vue'

const mounts = useMountsStore()
const appPrefs = useAppStore()
const activeMenu = ref('basic')

// 系统信息
const systemInfo = reactive({ app_name: 'MultiMount', version: '0.1.0', platform: '', python_version: '' })

// HTTPS
const httpsConfig = reactive({
  cert_valid: false,
  cert_expiry: '',
  cert_days_remaining: null,
  cert_expiry_warning: false,
  force_https: false,
  auto_redirect: true,
  cert_path: '',
  key_path: '',
  reverse_proxy: { nginx: [], caddy: [], notes: [] },
})

async function fetchHttpsStatus() {
  try {
    const data = await getHttpsStatus()
    Object.assign(httpsConfig, data)
  } catch {}
}

async function handleCertUpload(file) {
  try {
    await uploadCert(file.raw)
    ElMessage.success('证书已上传')
    await fetchHttpsStatus()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  }
}

async function handleKeyUpload(file) {
  try {
    await uploadKey(file.raw)
    ElMessage.success('私钥已上传')
    await fetchHttpsStatus()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  }
}

async function handleHttpsConfigChange() {
  try {
    await updateHttpsConfig({ force_https: httpsConfig.force_https, auto_redirect: httpsConfig.auto_redirect })
    ElMessage.success('HTTPS 配置已更新')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  }
}

// WebDAV
const webdavRunning = ref(false)
const webdavConfig = reactive({
  host: '0.0.0.0', port: 8080, ssl: false, root_mount: '',
  access_log: true, log_path: '/var/log/webdav/access.log',
  recycle_delete: true, url: 'http://localhost:8080/',
})

function webdavPayload() {
  return {
    host: webdavConfig.host,
    port: webdavConfig.port,
    ssl: webdavConfig.ssl,
    root_mount: webdavConfig.root_mount || null,
    access_log: webdavConfig.access_log,
    log_path: webdavConfig.log_path,
    recycle_delete: webdavConfig.recycle_delete,
  }
}

async function fetchWebDAVStatus() {
  try {
    const status = await getWebDAVStatus()
    webdavRunning.value = status.running
    webdavConfig.host = status.host || '0.0.0.0'
    webdavConfig.port = status.port || 8080
    webdavConfig.ssl = status.ssl || false
    webdavConfig.root_mount = status.root_mount || ''
    webdavConfig.access_log = status.access_log ?? true
    webdavConfig.log_path = status.log_path || '/var/log/webdav/access.log'
    webdavConfig.recycle_delete = status.recycle_delete ?? true
    webdavConfig.url = status.url || `${webdavConfig.ssl ? 'https' : 'http'}://localhost:${webdavConfig.port}/`
  } catch {}
}

async function handleWebdavToggle(running) {
  try {
    if (running) {
      await startWebDAV(webdavPayload())
      ElMessage.success('WebDAV 服务已启动')
    } else {
      await stopWebDAV()
      ElMessage.success('WebDAV 服务已停止')
    }
    await fetchWebDAVStatus()
  } catch (e) {
    ElMessage.error(`操作失败: ${e.response?.data?.detail || e.message}`)
    webdavRunning.value = !running
  }
}

async function handleSaveWebdav() {
  try {
    await updateWebDAVConfig(webdavPayload())
    ElMessage.success('WebDAV 配置已保存')
    await fetchWebDAVStatus()
  } catch (e) {
    ElMessage.error(`保存失败: ${e.response?.data?.detail || e.message}`)
  }
}

// 日志
const logType = ref('system')
const logDateRange = ref([])
const logEntries = ref([])
const logLoading = ref(false)

function logLevelType(level) {
  return { ERROR: 'danger', WARN: 'warning', INFO: '', DEBUG: 'info' }[level] || 'info'
}

async function fetchLogs() {
  logLoading.value = true
  try {
    const params = { log_type: logType.value }
    if (logDateRange.value?.length === 2) {
      params.start_date = logDateRange.value[0].toISOString().split('T')[0]
      params.end_date = logDateRange.value[1].toISOString().split('T')[0]
    }
    logEntries.value = await getLogs(params)
  } catch { logEntries.value = [] } finally { logLoading.value = false }
}

async function handleExportLog() {
  try {
    await exportLogs(logType.value)
    ElMessage.success(`${logType.value} 日志已导出`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '导出失败')
  }
}

async function handleClearLog() {
  await ElMessageBox.confirm(`确定清空${logType.value === 'system' ? '系统' : logType.value === 'access' ? '访问' : '传输'}日志?`, '确认', { type: 'warning' })
  try {
    await clearLogs(logType.value)
    logEntries.value = []
    ElMessage.success('日志已清空')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '清空失败')
  }
}

onMounted(async () => {
  mounts.fetchMounts()
  fetchWebDAVStatus()
  fetchHttpsStatus()
  fetchLogs()
  try {
    const info = await getSystemInfo()
    Object.assign(systemInfo, info)
  } catch {}
})
</script>

<style scoped>
.system-settings { display: flex; flex-direction: column; gap: 16px; }
.system-settings h2 { font-size: 20px; }
.cert-status { display: flex; align-items: center; gap: 8px; }
.cert-expiry { font-size: 12px; color: var(--text-secondary); margin-left: auto; }
.inline-alert { margin-top: 12px; }
.https-options { display: flex; flex-direction: column; gap: 4px; }
.webdav-status { display: flex; align-items: center; gap: 12px; }
.service-url { display: flex; align-items: center; gap: 8px; margin-top: 12px; font-size: 13px; color: var(--text-secondary); }
.service-url code,
.guide-list code { background: #f5f7fa; padding: 2px 6px; border-radius: 4px; }
.permission-map { display: flex; flex-wrap: wrap; gap: 8px; }
.proxy-block { display: flex; flex-direction: column; gap: 8px; }
.proxy-title { font-size: 12px; font-weight: 600; color: var(--text-secondary); }
.proxy-block pre { margin: 0; padding: 10px; overflow: auto; border-radius: 6px; background: #f5f7fa; font-size: 12px; line-height: 1.5; }
.guide-list { padding-left: 20px; line-height: 2; }
.log-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.log-actions { display: flex; gap: 8px; align-items: center; }
</style>
