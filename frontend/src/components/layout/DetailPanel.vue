<!--
  右侧详情操作面板 — 显示选中文件的元数据和快捷操作按钮。
-->
<template>
  <aside v-if="file" class="detail-panel">
    <div class="panel-header">
      <div class="file-icon" :class="{ folder: file.is_dir }">
        <el-icon :size="24">
          <component :is="file.is_dir ? Folder : Document" />
        </el-icon>
      </div>
      <div class="header-title">
        <span class="panel-kicker">{{ file.is_dir ? '文件夹详情' : '文件详情' }}</span>
        <h3 class="file-name">{{ file.name }}</h3>
      </div>
      <el-button class="panel-close" :icon="Close" circle text @click="$emit('close')" />
    </div>

    <div class="summary-card">
      <div class="summary-item">
        <span>类型</span>
        <strong>{{ file.is_dir ? '文件夹' : (file.mime_type || '未知') }}</strong>
      </div>
      <div class="summary-item">
        <span>{{ file.is_dir ? '总大小' : '大小' }}</span>
        <strong>{{ file.is_dir ? (file.total_size != null ? formatSize(file.total_size) : '-') : formatSize(file.size) }}</strong>
      </div>
      <div class="summary-item">
        <span>修改</span>
        <strong>{{ formatTime(file.modified_at) }}</strong>
      </div>
    </div>

    <div class="meta-list">
      <!-- 文件夹统计信息 -->
      <template v-if="file.is_dir">
        <div class="meta-item"><span class="label">包含文件</span><span>{{ file.file_count ?? '-' }} 个</span></div>
        <div class="meta-item"><span class="label">子文件夹</span><span>{{ file.dir_count ?? '-' }} 个</span></div>
      </template>
      <div class="meta-item"><span class="label">路径</span><span class="path-text">{{ file.path }}</span></div>
      <div class="meta-item" v-if="file.created_at"><span class="label">创建时间</span><span>{{ formatTime(file.created_at) }}</span></div>
      <div class="meta-item" v-if="file.permissions"><span class="label">权限</span><span>{{ file.permissions }}</span></div>
    </div>

    <div class="action-title">快捷操作</div>
    <div class="action-buttons">
      <el-button v-if="!file.is_dir" type="primary" :icon="Download" @click="$emit('download', file)">下载</el-button>
      <el-button :icon="Edit" @click="$emit('rename', file)">重命名</el-button>
      <el-button :icon="DeleteFilled" type="danger" @click="$emit('delete', file)">删除</el-button>
    </div>
  </aside>

  <aside v-else class="detail-panel empty">
    <div class="empty-state">
      <div class="empty-icon">
        <el-icon :size="30"><Document /></el-icon>
      </div>
      <strong>未选择项目</strong>
      <span>选择文件或文件夹后在这里查看详情</span>
    </div>
  </aside>
</template>

<script setup>
import { Folder, Document, Download, Edit, DeleteFilled, Close } from '@element-plus/icons-vue'
import { formatSize, formatTime } from '@/utils/format'

defineProps({
  file: { type: Object, default: null },
})

defineEmits(['download', 'rename', 'delete', 'close'])
</script>

<style scoped>
.detail-panel {
  flex: 0 0 clamp(260px, 24vw, var(--detail-width));
  width: clamp(260px, 24vw, var(--detail-width)); background: var(--card-bg);
  border-left: 1px solid var(--border-color); padding: 18px;
  overflow-y: auto; display: flex; flex-direction: column; gap: 16px;
  min-width: 0;
  container-type: inline-size;
}
.detail-panel.empty { align-items: center; justify-content: center; }
.panel-header { display: flex; align-items: center; gap: 12px; min-width: 0; }
.file-icon {
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--text-secondary) 12%, transparent);
}
.file-icon.folder {
  color: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color) 12%, transparent);
}
.header-title { min-width: 0; flex: 1; }
.panel-kicker {
  display: block;
  margin-bottom: 3px;
  color: var(--text-secondary);
  font-size: 12px;
}
.file-name { margin: 0; font-size: 15px; line-height: 1.35; word-break: break-word; }
.panel-close { margin-left: auto; display: none; }
.summary-card {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--primary-color) 14%, var(--border-color));
  border-radius: 10px;
  background: color-mix(in srgb, var(--primary-color) 5%, transparent);
}
.summary-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}
.summary-item span { color: var(--text-secondary); font-size: 12px; }
.summary-item strong {
  min-width: 0;
  color: var(--text-regular);
  font-size: 13px;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 2px;
}
.meta-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 10px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--border-color) 70%, transparent);
}
.meta-item:last-child { border-bottom: none; }
.meta-item .label { font-size: 12px; color: var(--text-secondary); }
.meta-item span:last-child { font-size: 13px; color: var(--text-regular); }
.path-text {
  padding: 8px;
  word-break: break-all;
  font-size: 12px;
  font-family: monospace;
  border-radius: 8px;
  background: color-mix(in srgb, var(--border-color) 34%, transparent);
}
.action-title {
  margin-top: auto;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}
.action-buttons {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}
.action-buttons :deep(.el-button) {
  width: 100%;
  min-width: 0;
  margin-left: 0;
  justify-content: flex-start;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
  color: var(--text-secondary);
}
.empty-state strong {
  color: var(--text-regular);
  font-size: 15px;
}
.empty-state span {
  max-width: 180px;
  font-size: 12px;
  line-height: 1.6;
}
.empty-icon {
  width: 54px;
  height: 54px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  color: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color) 10%, transparent);
}

@media (max-width: 768px) {
  .detail-panel {
    position: fixed;
    left: 0;
    right: 0;
    bottom: var(--mobile-nav-height);
    z-index: 900;
    width: auto;
    flex-basis: auto;
    max-height: 55vh;
    border-left: none;
    border-top: 1px solid var(--border-color);
    box-shadow: 0 -6px 18px rgba(0,0,0,0.12);
    border-radius: 12px 12px 0 0;
  }
  .detail-panel.empty {
    display: none;
  }
  .panel-close {
    display: inline-flex;
  }
}

@container (min-width: 320px) {
  .action-buttons {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .action-buttons :deep(.el-button:first-child:last-child) {
    grid-column: auto;
  }
  .action-buttons :deep(.el-button) {
    justify-content: center;
  }
}
</style>
