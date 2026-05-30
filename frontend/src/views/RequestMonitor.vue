<!--
  请求监控页面 — 访问日志查看 + IP 黑名单管理 (仅管理员可见)
-->
<template>
  <div class="request-monitor">
    <PageHeader
      title="请求监控"
      eyebrow="运维监控"
      description="集中查看访问流量、操作审计与 IP 黑名单状态。"
      :meta="[
        `${stats.today_requests} 今日请求`,
        `${stats.active_ips_today} 今日活跃 IP`,
        `${activeBlacklistCount} 个生效黑名单`,
      ]"
      actions-layout="flex"
    >
      <template #actions>
        <el-button :icon="Refresh" @click="refreshCurrent" :loading="currentLoading">刷新当前</el-button>
        <el-button type="primary" :icon="Monitor" @click="fetchStats" :loading="statsLoading">刷新统计</el-button>
      </template>
    </PageHeader>

    <!-- 顶部统计卡片 -->
    <div class="stats-row">
      <div v-if="statsLoading" v-for="i in 4" :key="i" class="stat-card is-loading">
        <div class="skeleton skeleton-title" />
        <div class="skeleton skeleton-text" />
      </div>
      <template v-else>
        <div class="stat-card stat-total">
          <div class="stat-icon"><el-icon><Monitor /></el-icon></div>
          <div>
            <div class="stat-value">{{ stats.total_requests }}</div>
            <div class="stat-label">总请求数</div>
          </div>
        </div>
        <div class="stat-card stat-today">
          <div class="stat-icon"><el-icon><Connection /></el-icon></div>
          <div>
            <div class="stat-value">{{ stats.today_requests }}</div>
            <div class="stat-label">今日请求</div>
          </div>
        </div>
        <div class="stat-card stat-active">
          <div class="stat-icon"><el-icon><Search /></el-icon></div>
          <div>
            <div class="stat-value">{{ stats.active_ips_today }}</div>
            <div class="stat-label">今日活跃 IP</div>
          </div>
        </div>
        <div class="stat-card stat-risk">
          <div class="stat-icon"><el-icon><Lock /></el-icon></div>
          <div>
            <div class="stat-value">{{ activeBlacklistCount }}</div>
            <div class="stat-label">生效黑名单</div>
          </div>
        </div>
      </template>
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" class="monitor-tabs" @tab-change="onTabChange">
      <!-- 访问日志 -->
      <el-tab-pane label="访问日志" name="logs">
        <section class="monitor-section">
          <div class="section-head">
            <div>
              <span>ACCESS LOGS</span>
              <h3>访问日志</h3>
              <p>追踪请求来源、接口路径、状态码与响应耗时。</p>
            </div>
            <el-tag type="info" effect="plain">{{ logTotal }} 条</el-tag>
          </div>

          <el-collapse class="filter-collapse">
            <el-collapse-item name="logs-filter">
              <template #title>
                <div class="collapse-title"><el-icon><Search /></el-icon><span>筛选条件</span></div>
              </template>
              <div class="filter-bar responsive-filters">
                <el-input v-model="logFilter.ip" placeholder="按 IP 筛选" clearable size="small" @clear="fetchLogs" @keyup.enter="fetchLogs" />
                <el-button size="small" type="primary" @click="fetchLogs" :loading="logsLoading">查询</el-button>
              </div>
            </el-collapse-item>
          </el-collapse>

          <el-table :data="logs" v-loading="logsLoading" stripe size="small" class="monitor-table">
            <el-table-column prop="ip_address" label="IP 地址" width="150">
              <template #default="{ row }"><span class="mono-text">{{ row.ip_address }}</span></template>
            </el-table-column>
            <el-table-column prop="method" label="方法" width="86">
              <template #default="{ row }">
                <el-tag :type="methodTagType(row.method)" size="small" effect="light" class="monitor-tag" :class="methodClass(row.method)">{{ row.method }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="path" label="请求路径" min-width="220" show-overflow-tooltip />
            <el-table-column prop="status_code" label="状态码" width="96">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status_code)" size="small" effect="light" class="monitor-tag" :class="statusClass(row.status_code)">{{ row.status_code }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="response_time_ms" label="耗时" width="100">
              <template #default="{ row }"><span class="latency-text">{{ formatDuration(row.response_time_ms) }}</span></template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="180" class-name="hide-sm" label-class-name="hide-sm">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="86">
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
        </section>
      </el-tab-pane>

      <!-- 操作审计 -->
      <el-tab-pane label="操作审计" name="operations">
        <section class="monitor-section">
          <div class="section-head">
            <div>
              <span>OPERATION AUDIT</span>
              <h3>操作审计</h3>
              <p>查看用户对文件、分享和权限的关键操作记录。</p>
            </div>
            <el-tag type="info" effect="plain">{{ opTotal }} 条</el-tag>
          </div>

          <el-collapse class="filter-collapse">
            <el-collapse-item name="operations-filter">
              <template #title>
                <div class="collapse-title"><el-icon><Search /></el-icon><span>筛选条件</span></div>
              </template>
              <div class="filter-bar responsive-filters">
                <el-input v-model="opFilter.username" placeholder="按用户筛选" clearable size="small" @clear="fetchOperationLogs" @keyup.enter="fetchOperationLogs" />
                <el-input v-model="opFilter.action" placeholder="按操作筛选" clearable size="small" @clear="fetchOperationLogs" @keyup.enter="fetchOperationLogs" />
                <el-input-number v-model="opFilter.mount_id" placeholder="挂载 ID" :min="1" size="small" />
                <el-select v-model="opFilter.status" placeholder="状态" clearable size="small">
                  <el-option label="成功" value="success" />
                  <el-option label="失败" value="failed" />
                </el-select>
                <el-button size="small" type="primary" @click="fetchOperationLogs" :loading="opLoading">查询</el-button>
              </div>
            </el-collapse-item>
          </el-collapse>

          <el-table :data="operationLogs" v-loading="opLoading" stripe size="small" class="monitor-table">
            <el-table-column prop="created_at" label="时间" width="180" class-name="hide-sm" label-class-name="hide-sm">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="username" label="用户" width="120">
              <template #default="{ row }">{{ row.username || '匿名' }}</template>
            </el-table-column>
            <el-table-column prop="action" label="操作" width="150">
              <template #default="{ row }">
                <el-tag size="small" effect="light" :type="operationTagType(row.action)" class="monitor-tag" :class="operationClass(row.action)">{{ operationLabel(row.action) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="mount_id" label="挂载" width="80" class-name="hide-sm" label-class-name="hide-sm">
              <template #default="{ row }">{{ row.mount_id || '-' }}</template>
            </el-table-column>
            <el-table-column prop="path" label="路径" min-width="220" show-overflow-tooltip />
            <el-table-column prop="target_path" label="目标路径" min-width="180" show-overflow-tooltip class-name="hide-sm" label-class-name="hide-sm" />
            <el-table-column prop="ip_address" label="IP" width="140" class-name="hide-sm" label-class-name="hide-sm">
              <template #default="{ row }"><span class="mono-text">{{ row.ip_address || '-' }}</span></template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" effect="light" :type="row.status === 'success' ? 'success' : 'danger'" class="monitor-tag" :class="row.status === 'success' ? 'status-ok' : 'status-error'">{{ row.status === 'success' ? '成功' : '失败' }}</el-tag>
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
        </section>
      </el-tab-pane>

      <!-- IP 黑名单 -->
      <el-tab-pane label="IP 黑名单" name="blacklist">
        <section class="monitor-section">
          <div class="section-head">
            <div>
              <span>IP BLACKLIST</span>
              <h3>IP 黑名单</h3>
              <p>维护阻断 IP，快速处置异常访问来源。</p>
            </div>
            <el-tag type="danger" effect="plain">{{ activeBlacklistCount }} 个生效</el-tag>
          </div>

          <div class="blacklist-actions">
            <el-input v-model="newIp" placeholder="输入 IP 地址" size="small" />
            <el-input v-model="newReason" placeholder="拉黑原因 (可选)" size="small" />
            <el-button type="danger" size="small" @click="handleAdd" :loading="addLoading">添加拉黑</el-button>
            <el-button size="small" :icon="Refresh" @click="fetchBlacklist" :loading="blLoading">刷新</el-button>
          </div>

          <el-table :data="blacklist" v-loading="blLoading" stripe size="small" class="monitor-table">
            <el-table-column prop="ip_address" label="IP 地址" width="180">
              <template #default="{ row }"><span class="mono-text">{{ row.ip_address }}</span></template>
            </el-table-column>
            <el-table-column prop="reason" label="拉黑原因" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">{{ row.reason || '-' }}</template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'danger' : 'info'" size="small" effect="light" class="monitor-tag" :class="row.is_active ? 'status-blocked' : 'status-muted'">{{ row.is_active ? '生效中' : '已解封' }}</el-tag>
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
        </section>
      </el-tab-pane>

      <!-- 统计排行 -->
      <el-tab-pane label="统计排行" name="rankings">
        <section class="monitor-section">
          <div class="section-head">
            <div>
              <span>RANKINGS</span>
              <h3>统计排行</h3>
              <p>快速定位高频来源 IP 与高频访问路径。</p>
            </div>
          </div>
          <div class="ranking-grid">
            <div class="ranking-section">
              <h4>请求量 Top 10 IP</h4>
              <div v-for="(item, i) in stats.top_ips" :key="i" class="ranking-item">
                <span class="rank-num">{{ i + 1 }}</span>
                <span class="rank-key mono-text">{{ item.ip }}</span>
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
        </section>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, Lock, Monitor, Refresh, Search } from '@element-plus/icons-vue'
import { getAccessLogs, getAccessStats, getOperationLogs, getIPBlacklist, addIPBlacklist, removeIPBlacklist } from '@/api/system'
import PageHeader from '@/components/common/PageHeader.vue'

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

const activeBlacklistCount = computed(() => blacklist.value.filter((item) => item.is_active).length)
const currentLoading = computed(() => ({
  logs: logsLoading.value,
  operations: opLoading.value,
  blacklist: blLoading.value,
  rankings: statsLoading.value,
}[activeTab.value] || false))

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

function refreshCurrent() {
  if (activeTab.value === 'logs') return fetchLogs()
  if (activeTab.value === 'operations') return fetchOperationLogs()
  if (activeTab.value === 'blacklist') return fetchBlacklist()
  return fetchStats()
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

function methodClass(m) {
  return `method-${String(m || 'other').toLowerCase()}`
}

function statusTagType(s) {
  if (s < 300) return 'success'
  if (s < 400) return 'warning'
  if (s < 500) return ''
  return 'danger'
}

function statusClass(s) {
  if (s < 300) return 'status-ok'
  if (s < 400) return 'status-redirect'
  if (s < 500) return 'status-warn'
  return 'status-error'
}

function formatDuration(ms) {
  if (typeof ms !== 'number') return '-'
  return `${ms.toFixed(1)}ms`
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
  const value = String(action || '')
  if (value.includes('delete') || value.includes('revoke')) return 'danger'
  if (value.includes('permission')) return 'warning'
  if (value.includes('share')) return 'success'
  return 'info'
}

function operationClass(action) {
  const value = String(action || '')
  if (value.includes('delete') || value.includes('revoke')) return 'op-danger'
  if (value.includes('permission')) return 'op-permission'
  if (value.includes('share')) return 'op-share'
  if (value.includes('upload') || value.includes('mkdir')) return 'op-create'
  return 'op-neutral'
}

// ── 初始化 ───────────────────────────────────────────────────
onMounted(() => {
  fetchStats()
  fetchLogs()
  fetchBlacklist()
})
</script>

<style scoped>
.request-monitor { display: flex; flex-direction: column; gap: 18px; }

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.stat-card {
  position: relative;
  min-height: 108px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}
.stat-card::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--primary-color);
}
.stat-card.is-loading {
  display: block;
}
.stat-card.is-loading .skeleton-title {
  width: 60%;
  margin: 10px 0 12px 10px;
}
.stat-card.is-loading .skeleton-text {
  width: 42%;
  margin-left: 10px;
}
.stat-today::before { background: var(--success-color); }
.stat-active::before { background: var(--warning-color); }
.stat-risk::before { background: var(--danger-color); }
.stat-icon {
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color) 10%, transparent);
}
.stat-today .stat-icon {
  color: var(--success-color);
  background: color-mix(in srgb, var(--success-color) 12%, transparent);
}
.stat-active .stat-icon {
  color: var(--warning-color);
  background: color-mix(in srgb, var(--warning-color) 14%, transparent);
}
.stat-risk .stat-icon {
  color: var(--danger-color);
  background: color-mix(in srgb, var(--danger-color) 12%, transparent);
}
.stat-value { font-size: 28px; font-weight: 800; color: var(--text-primary); line-height: 1.1; }
.stat-label { font-size: 13px; color: var(--text-secondary); margin-top: 6px; }

.monitor-tabs {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 4px 16px 16px;
}
.monitor-tabs :deep(.el-tabs__nav-wrap::after) { display: none; }
.monitor-section { display: flex; flex-direction: column; gap: 14px; }
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  padding-top: 4px;
}
.section-head span {
  color: var(--primary-color);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
}
.section-head h3 {
  margin: 4px 0 0;
  font-size: 18px;
  line-height: 1.35;
}
.section-head p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.filter-collapse {
  border: 1px solid color-mix(in srgb, var(--border-color) 70%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--primary-color) 4%, transparent);
  overflow: hidden;
}
.filter-collapse :deep(.el-collapse-item__header) {
  height: 42px;
  padding: 0 12px;
  border-bottom: none;
  background: transparent;
}
.filter-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
  background: transparent;
}
.filter-collapse :deep(.el-collapse-item__content) {
  padding: 0 12px 12px;
}
.collapse-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-regular);
  font-size: 13px;
  font-weight: 700;
}
.filter-bar { margin: 0; }
.filter-bar :deep(.el-button) { min-width: 76px; }
.blacklist-actions {
  display: grid;
  grid-template-columns: minmax(160px, 220px) minmax(180px, 1fr) max-content max-content;
  gap: 8px;
  align-items: center;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--danger-color) 18%, var(--border-color));
  border-radius: 10px;
  background: color-mix(in srgb, var(--danger-color) 5%, transparent);
}
.monitor-table {
  width: 100%;
  border: 1px solid color-mix(in srgb, var(--border-color) 80%, transparent);
  border-radius: 10px;
  overflow: hidden;
}
.monitor-table :deep(.el-table__header th) {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  background: color-mix(in srgb, var(--border-color) 26%, transparent);
}
.mono-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 12px;
}
.latency-text {
  color: var(--text-regular);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 12px;
}
.monitor-tag {
  border: none;
  font-weight: 700;
}
.method-get,
.status-ok,
.op-share,
.op-create {
  color: var(--success-color);
  background: color-mix(in srgb, var(--success-color) 12%, transparent);
}
.method-post,
.op-neutral {
  color: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color) 12%, transparent);
}
.method-put,
.status-redirect,
.op-permission {
  color: var(--warning-color);
  background: color-mix(in srgb, var(--warning-color) 14%, transparent);
}
.method-delete,
.status-error,
.status-blocked,
.op-danger {
  color: var(--danger-color);
  background: color-mix(in srgb, var(--danger-color) 12%, transparent);
}
.status-warn {
  color: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color) 10%, transparent);
}
.status-muted {
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--text-secondary) 12%, transparent);
}
.pagination-bar { display: flex; justify-content: flex-end; margin-top: 12px; }

.ranking-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.ranking-section {
  padding: 16px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: color-mix(in srgb, var(--primary-color) 4%, transparent);
}
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
@media (max-width: 1180px) {
  .stats-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 768px) {
  .stats-row { grid-template-columns: 1fr; }
  .stat-card { min-height: 92px; }
  .monitor-tabs { padding: 4px 12px 14px; }
  .section-head { align-items: flex-start; flex-direction: column; }
  .blacklist-actions {
    grid-template-columns: 1fr;
  }
  .blacklist-actions :deep(.el-button) {
    width: 100%;
  }
  .ranking-grid { grid-template-columns: 1fr; }
  .pagination-bar { justify-content: flex-start; overflow-x: auto; }
}
</style>
