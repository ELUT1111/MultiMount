<!--
  请求监控页面 — 访问日志查看 + IP 黑名单管理 (仅管理员可见)
-->
<template>
  <div class="request-monitor">
    <h2>请求监控</h2>

    <!-- 顶部统计卡片 -->
    <div class="stats-row">
      <div v-if="statsLoading" v-for="i in 3" :key="i" class="stat-card">
        <div class="skeleton skeleton-title" style="width: 60%; margin: 0 auto 8px;" />
        <div class="skeleton skeleton-text" style="width: 40%; margin: 0 auto;" />
      </div>
      <template v-else>
        <div class="stat-card">
          <div class="stat-value">{{ stats.total_requests }}</div>
          <div class="stat-label">总请求数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.today_requests }}</div>
          <div class="stat-label">今日请求</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.active_ips_today }}</div>
          <div class="stat-label">今日活跃 IP</div>
        </div>
      </template>
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- 访问日志 -->
      <el-tab-pane label="访问日志" name="logs">
        <div class="filter-bar responsive-filters">
          <el-input v-model="logFilter.ip" placeholder="按 IP 筛选" clearable size="small" @clear="fetchLogs" @keyup.enter="fetchLogs" />
          <el-button size="small" @click="fetchLogs" :loading="logsLoading">查询</el-button>
        </div>
        <el-table :data="logs" v-loading="logsLoading" stripe size="small" style="width: 100%">
          <el-table-column prop="ip_address" label="IP 地址" width="150" />
          <el-table-column prop="method" label="方法" width="80">
            <template #default="{ row }">
              <el-tag :type="methodTagType(row.method)" size="small">{{ row.method }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="path" label="请求路径" min-width="200" show-overflow-tooltip />
          <el-table-column prop="status_code" label="状态码" width="90">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status_code)" size="small">{{ row.status_code }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="response_time_ms" label="耗时" width="90">
            <template #default="{ row }">{{ row.response_time_ms.toFixed(1) }}ms</template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="180" class-name="hide-sm" label-class-name="hide-sm">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button link type="danger" size="small" @click="quickBlock(row.ip_address)">拉黑</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-bar">
          <el-pagination
            v-model:current-page="logFilter.page"
            :page-size="logFilter.page_size"
            :total="logTotal"
            layout="total, prev, pager, next"
            @current-change="fetchLogs"
          />
        </div>
      </el-tab-pane>

      <!-- 操作审计 -->
      <el-tab-pane label="操作审计" name="operations">
        <div class="filter-bar responsive-filters">
          <el-input v-model="opFilter.username" placeholder="按用户筛选" clearable size="small" @clear="fetchOperationLogs" @keyup.enter="fetchOperationLogs" />
          <el-input v-model="opFilter.action" placeholder="按操作筛选" clearable size="small" @clear="fetchOperationLogs" @keyup.enter="fetchOperationLogs" />
          <el-input-number v-model="opFilter.mount_id" placeholder="挂载 ID" :min="1" size="small" />
          <el-select v-model="opFilter.status" placeholder="状态" clearable size="small">
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
          </el-select>
          <el-button size="small" @click="fetchOperationLogs" :loading="opLoading">查询</el-button>
        </div>
        <el-table :data="operationLogs" v-loading="opLoading" stripe size="small" style="width: 100%">
          <el-table-column prop="created_at" label="时间" width="180" class-name="hide-sm" label-class-name="hide-sm">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="username" label="用户" width="120">
            <template #default="{ row }">{{ row.username || '匿名' }}</template>
          </el-table-column>
          <el-table-column prop="action" label="操作" width="150">
            <template #default="{ row }">
              <el-tag size="small" :type="operationTagType(row.action)">{{ operationLabel(row.action) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="mount_id" label="挂载" width="80" class-name="hide-sm" label-class-name="hide-sm">
            <template #default="{ row }">{{ row.mount_id || '-' }}</template>
          </el-table-column>
          <el-table-column prop="path" label="路径" min-width="220" show-overflow-tooltip />
          <el-table-column prop="target_path" label="目标路径" min-width="180" show-overflow-tooltip class-name="hide-sm" label-class-name="hide-sm" />
          <el-table-column prop="ip_address" label="IP" width="140" class-name="hide-sm" label-class-name="hide-sm">
            <template #default="{ row }">{{ row.ip_address || '-' }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="row.status === 'success' ? 'success' : 'danger'">{{ row.status === 'success' ? '成功' : '失败' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-bar">
          <el-pagination
            v-model:current-page="opFilter.page"
            :page-size="opFilter.page_size"
            :total="opTotal"
            layout="total, prev, pager, next"
            @current-change="fetchOperationLogs"
          />
        </div>
      </el-tab-pane>

      <!-- IP 黑名单 -->
      <el-tab-pane label="IP 黑名单" name="blacklist">
        <div class="filter-bar responsive-filters">
          <el-input v-model="newIp" placeholder="输入 IP 地址" size="small" />
          <el-input v-model="newReason" placeholder="拉黑原因 (可选)" size="small" />
          <el-button type="danger" size="small" @click="handleAdd" :loading="addLoading">添加拉黑</el-button>
          <el-button size="small" @click="fetchBlacklist" :loading="blLoading">刷新</el-button>
        </div>
        <el-table :data="blacklist" v-loading="blLoading" stripe size="small" style="width: 100%">
          <el-table-column prop="ip_address" label="IP 地址" width="180" />
          <el-table-column prop="reason" label="拉黑原因" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ row.reason || '-' }}</template>
          </el-table-column>
          <el-table-column prop="is_active" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'danger' : 'info'" size="small">{{ row.is_active ? '生效中' : '已解封' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="添加时间" width="180" class-name="hide-sm" label-class-name="hide-sm">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button v-if="row.is_active" link type="primary" size="small" @click="handleRemove(row.ip_address)">解封</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 统计排行 -->
      <el-tab-pane label="统计排行" name="rankings">
        <div class="ranking-grid">
          <div class="ranking-section">
            <h4>请求量 Top 10 IP</h4>
            <div v-for="(item, i) in stats.top_ips" :key="i" class="ranking-item">
              <span class="rank-num">{{ i + 1 }}</span>
              <span class="rank-key">{{ item.ip }}</span>
              <span class="rank-val">{{ item.count }} 次</span>
            </div>
            <el-empty v-if="stats.top_ips?.length === 0" description="暂无数据" :image-size="48" />
          </div>
          <div class="ranking-section">
            <h4>请求量 Top 10 路径</h4>
            <div v-for="(item, i) in stats.top_paths" :key="i" class="ranking-item">
              <span class="rank-num">{{ i + 1 }}</span>
              <span class="rank-key" :title="item.path">{{ item.path }}</span>
              <span class="rank-val">{{ item.count }} 次</span>
            </div>
            <el-empty v-if="stats.top_paths?.length === 0" description="暂无数据" :image-size="48" />
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAccessLogs, getAccessStats, getOperationLogs, getIPBlacklist, addIPBlacklist, removeIPBlacklist } from '@/api/system'

// ── 状态 ────────────────────────────────────────────────────
const activeTab = ref('logs')
const statsLoading = ref(false)
const stats = reactive({ total_requests: 0, today_requests: 0, active_ips_today: 0, top_ips: [], top_paths: [] })

// 日志
const logs = ref([])
const logsLoading = ref(false)
const logTotal = ref(0)
const logFilter = reactive({ ip: '', page: 1, page_size: 50 })

// 操作审计
const operationLogs = ref([])
const opLoading = ref(false)
const opTotal = ref(0)
const opFilter = reactive({ username: '', action: '', mount_id: null, status: '', page: 1, page_size: 50 })

// 黑名单
const blacklist = ref([])
const blLoading = ref(false)
const addLoading = ref(false)
const newIp = ref('')
const newReason = ref('')

// ── 数据获取 ─────────────────────────────────────────────────
async function fetchStats() {
  statsLoading.value = true
  try {
    const data = await getAccessStats()
    Object.assign(stats, data)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '获取统计数据失败')
  } finally { statsLoading.value = false }
}

async function fetchLogs() {
  logsLoading.value = true
  try {
    const data = await getAccessLogs({ page: logFilter.page, page_size: logFilter.page_size, ip: logFilter.ip })
    logs.value = data.items
    logTotal.value = data.total
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '获取访问日志失败')
  } finally { logsLoading.value = false }
}

async function fetchOperationLogs() {
  opLoading.value = true
  try {
    const data = await getOperationLogs({
      page: opFilter.page,
      page_size: opFilter.page_size,
      username: opFilter.username,
      action: opFilter.action,
      mount_id: opFilter.mount_id || undefined,
      status: opFilter.status,
    })
    operationLogs.value = data.items
    opTotal.value = data.total
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '获取操作审计失败')
  } finally { opLoading.value = false }
}

async function fetchBlacklist() {
  blLoading.value = true
  try {
    blacklist.value = await getIPBlacklist()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '获取黑名单失败')
  } finally { blLoading.value = false }
}

function onTabChange(tab) {
  if (tab === 'logs') fetchLogs()
  else if (tab === 'operations') fetchOperationLogs()
  else if (tab === 'blacklist') fetchBlacklist()
  else if (tab === 'rankings') fetchStats()
}

// ── IP 格式校验 ─────────────────────────────────────────────
const IPv4_RE = /^(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(?:\.(?!$)|$)){4}$/
const IPv6_RE = /^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|::|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:))$/
function isValidIP(ip) { return IPv4_RE.test(ip) || IPv6_RE.test(ip) }

// ── 黑名单操作 ───────────────────────────────────────────────
async function handleAdd() {
  const ip = newIp.value.trim()
  if (!ip) return ElMessage.warning('请输入 IP 地址')
  if (!isValidIP(ip)) return ElMessage.warning('请输入有效的 IP 地址')
  addLoading.value = true
  try {
    await addIPBlacklist({ ip_address: newIp.value.trim(), reason: newReason.value.trim() || null })
    ElMessage.success(`已拉黑 ${newIp.value}`)
    newIp.value = ''
    newReason.value = ''
    await fetchBlacklist()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加黑名单失败')
  } finally { addLoading.value = false }
}

async function handleRemove(ip) {
  await ElMessageBox.confirm(`确定解封 ${ip}?`, '确认', { type: 'warning' })
  try {
    await removeIPBlacklist(ip)
    ElMessage.success(`已解封 ${ip}`)
    await fetchBlacklist()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '解封失败')
  }
}

async function quickBlock(ip) {
  if (!isValidIP(ip)) return ElMessage.warning('IP 格式异常, 无法拉黑')
  await ElMessageBox.confirm(`确定拉黑 ${ip}?`, '确认', { type: 'warning' })
  try {
    await addIPBlacklist({ ip_address: ip, reason: '请求监控中手动拉黑' })
    ElMessage.success(`已拉黑 ${ip}`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '拉黑失败')
  }
}

// ── 辅助 ─────────────────────────────────────────────────────
function formatTime(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

function methodTagType(m) {
  return { GET: '', POST: 'success', PUT: 'warning', DELETE: 'danger' }[m] || 'info'
}

function statusTagType(s) {
  if (s < 300) return 'success'
  if (s < 400) return 'warning'
  if (s < 500) return ''
  return 'danger'
}

function operationLabel(action) {
  return {
    file_download: '文件下载',
    file_upload: '文件上传',
    file_mkdir: '新建目录',
    file_move: '移动/重命名',
    file_copy: '复制',
    file_delete: '删除',
    share_create: '创建分享',
    share_access: '访问分享',
    share_download: '分享下载',
    share_delete: '删除分享',
    share_deactivate: '停用分享',
    permission_grant: '授予权限',
    permission_revoke: '撤销权限',
    permission_request: '申请权限',
  }[action] || action
}

function operationTagType(action) {
  if (action.includes('delete') || action.includes('revoke')) return 'danger'
  if (action.includes('permission')) return 'warning'
  if (action.includes('share')) return 'success'
  return 'info'
}

// ── 初始化 ───────────────────────────────────────────────────
onMounted(() => {
  fetchStats()
  fetchLogs()
})
</script>

<style scoped>
.request-monitor { display: flex; flex-direction: column; gap: 16px; }
.request-monitor h2 { font-size: 20px; margin: 0; }

.stats-row { display: flex; gap: 16px; }
.stat-card {
  flex: 1; background: var(--card-bg); border-radius: 12px; padding: 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06); text-align: center;
}
.stat-value { font-size: 28px; font-weight: 700; color: var(--primary-color); }
.stat-label { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }

.filter-bar { margin-bottom: 12px; }
.pagination-bar { display: flex; justify-content: flex-end; margin-top: 12px; }

.ranking-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.ranking-section h4 { font-size: 15px; margin: 0 0 12px; color: var(--text-regular); }
.ranking-item {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 0; border-bottom: 1px solid var(--border-color);
}
.rank-num {
  width: 24px; height: 24px; border-radius: 50%;
  background: rgba(64,158,255,0.1); color: var(--primary-color);
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 600; flex-shrink: 0;
}
.rank-key { flex: 1; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rank-val { font-size: 13px; color: var(--text-secondary); white-space: nowrap; }

/* 响应式 */
@media (max-width: 768px) {
  .stats-row { flex-wrap: wrap; }
  .stat-card { min-width: calc(50% - 8px); }
  .ranking-grid { grid-template-columns: 1fr; }
}
</style>
