<!--
  右侧详情操作面板 — 显示选中文件的元数据和快捷操作按钮。
-->
<template>
  <aside v-if="file" class="detail-panel">
    <div class="panel-header">
      <el-icon :size="32" :color="file.is_dir ? '#409eff' : '#909399'">
        <component :is="file.is_dir ? Folder : Document" />
      </el-icon>
      <h3 class="file-name">{{ file.name }}</h3>
      <el-button class="panel-close" :icon="Close" circle text @click="$emit('close')" />
    </div>

    <el-divider />

    <div class="meta-list">
      <div class="meta-item"><span class="label">类型</span><span>{{ file.is_dir ? '文件夹' : (file.mime_type || '未知') }}</span></div>
      <div class="meta-item" v-if="!file.is_dir"><span class="label">大小</span><span>{{ formatSize(file.size) }}</span></div>
      <!-- 文件夹统计信息 -->
      <template v-if="file.is_dir">
        <div class="meta-item"><span class="label">包含文件</span><span>{{ file.file_count ?? '-' }} 个</span></div>
        <div class="meta-item"><span class="label">子文件夹</span><span>{{ file.dir_count ?? '-' }} 个</span></div>
        <div class="meta-item"><span class="label">总大小</span><span>{{ file.total_size != null ? formatSize(file.total_size) : '-' }}</span></div>
      </template>
      <div class="meta-item"><span class="label">路径</span><span class="path-text">{{ file.path }}</span></div>
      <div class="meta-item"><span class="label">修改时间</span><span>{{ formatTime(file.modified_at) }}</span></div>
      <div class="meta-item" v-if="file.created_at"><span class="label">创建时间</span><span>{{ formatTime(file.created_at) }}</span></div>
      <div class="meta-item" v-if="file.permissions"><span class="label">权限</span><span>{{ file.permissions }}</span></div>
    </div>

    <el-divider />

    <div class="action-buttons">
      <el-button v-if="!file.is_dir" type="primary" :icon="Download" @click="$emit('download', file)">下载</el-button>
      <el-button :icon="Edit" @click="$emit('rename', file)">重命名</el-button>
      <el-button :icon="DeleteFilled" type="danger" @click="$emit('delete', file)">删除</el-button>
    </div>
  </aside>

  <aside v-else class="detail-panel empty">
    <el-empty description="选择文件查看详情" :image-size="80" />
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
  border-left: 1px solid var(--border-color); padding: 20px;
  overflow-y: auto; display: flex; flex-direction: column;
  min-width: 0;
  container-type: inline-size;
}
.detail-panel.empty { align-items: center; justify-content: center; }
.panel-header { display: flex; align-items: center; gap: 12px; }
.file-name { font-size: 15px; word-break: break-all; }
.panel-close { margin-left: auto; display: none; }
.meta-list { display: flex; flex-direction: column; gap: 10px; }
.meta-item { display: flex; flex-direction: column; gap: 2px; }
.meta-item .label { font-size: 12px; color: var(--text-secondary); }
.meta-item span:last-child { font-size: 13px; color: var(--text-regular); }
.path-text { word-break: break-all; font-size: 12px; font-family: monospace; }
.action-buttons {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: auto;
}
.action-buttons :deep(.el-button) {
  width: 100%;
  min-width: 0;
  margin-left: 0;
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

@container (max-width: 280px) {
  .action-buttons {
    grid-template-columns: 1fr;
  }
}
</style>
