<!--
  角色权限配置组件 — 基础权限勾选、挂载点权限设置、QoS 速率限制。
-->
<template>
  <div v-if="role" class="role-permission">
    <div class="permission-header">
      <div>
        <h3>{{ role.name }} - 权限配置</h3>
        <p>配置基础操作、挂载点访问范围和连接速率限制。</p>
      </div>
      <div class="role-actions desktop-actions">
        <el-button @click="$emit('reset')">重置</el-button>
        <el-button type="primary" @click="$emit('save', localRole)">保存配置</el-button>
      </div>
    </div>

    <!-- 基础权限 -->
    <section class="permission-section">
      <h4>基础权限</h4>
      <div class="perm-grid">
        <el-checkbox v-model="localRole.permissions.can_login" label="允许登录" />
        <el-checkbox v-model="localRole.permissions.can_upload" label="允许上传" />
        <el-checkbox v-model="localRole.permissions.can_download" label="允许下载" />
        <el-checkbox v-model="localRole.permissions.can_modify" label="允许修改" />
        <el-checkbox v-model="localRole.permissions.can_delete" label="允许删除" />
        <el-checkbox v-model="localRole.permissions.can_manage_mounts" label="允许挂载管理" />
      </div>
    </section>

    <!-- 挂载点权限 -->
    <section class="permission-section">
      <h4>挂载点权限</h4>
      <div class="mount-perms">
        <div v-for="mount in mounts" :key="mount.id" class="mount-perm-row">
          <div class="mount-copy">
            <span class="mount-perm-name">{{ mount.name }}</span>
            <span class="mount-perm-type">{{ mount.type || 'mount' }}</span>
          </div>
          <el-radio-group v-model="localRole.mount_permissions[mount.id]" size="small">
            <el-radio-button label="none">不可见</el-radio-button>
            <el-radio-button label="read">只读</el-radio-button>
            <el-radio-button label="readwrite">读写</el-radio-button>
          </el-radio-group>
        </div>
        <el-empty v-if="mounts.length === 0" description="暂无挂载点" :image-size="48" />
      </div>
    </section>

    <!-- QoS 速率限制 -->
    <section class="permission-section">
      <h4>QoS 速率限制</h4>
      <el-form class="qos-form" label-position="top">
        <el-form-item label="最大下载速率(KB/s)">
          <el-input-number v-model="localRole.qos_limits.max_download_kbps" :min="0" controls-position="right" />
        </el-form-item>
        <el-form-item label="最大上传速率(KB/s)">
          <el-input-number v-model="localRole.qos_limits.max_upload_kbps" :min="0" controls-position="right" />
        </el-form-item>
        <el-form-item label="最大并发连接数">
          <el-input-number v-model="localRole.qos_limits.max_concurrent" :min="1" controls-position="right" />
        </el-form-item>
      </el-form>
    </section>

    <div class="role-actions mobile-actions">
      <el-button @click="$emit('reset')">重置</el-button>
      <el-button type="primary" @click="$emit('save', localRole)">保存配置</el-button>
    </div>
  </div>
  <div v-else class="role-permission empty">
    <el-empty description="选择一个角色进行配置" :image-size="80" />
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  role: { type: Object, default: null },
  mounts: { type: Array, default: () => [] },
})

defineEmits(['save', 'reset'])

// 深拷贝角色数据, 避免直接修改 props
const localRole = reactive({
  id: null,
  name: '',
  permissions: { can_login: true, can_upload: true, can_download: true, can_modify: false, can_delete: false, can_manage_mounts: false },
  mount_permissions: {},
  qos_limits: { max_download_kbps: 0, max_upload_kbps: 0, max_concurrent: 5 },
})

watch(() => props.role, (val) => {
  if (val) {
    localRole.id = val.id
    localRole.name = val.name
    localRole.permissions = { ...val.permissions }
    localRole.mount_permissions = { ...(val.mount_permissions || {}) }
    localRole.qos_limits = { ...val.qos_limits }
  }
}, { deep: true, immediate: true })
</script>

<style scoped>
.role-permission {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}
.role-permission.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 360px;
}
.permission-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border-color);
}
.role-permission h3 {
  margin: 0;
  font-size: 16px;
  line-height: 1.35;
}
.role-permission p {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.45;
}
.permission-section {
  display: grid;
  gap: 12px;
}
.role-permission h4 {
  margin: 0;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
}
.perm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px 14px;
}
.perm-grid :deep(.el-checkbox) {
  min-width: 0;
  height: 32px;
  margin-right: 0;
}
.mount-perms {
  display: grid;
  gap: 10px;
}
.mount-perm-row {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-color);
}
.mount-copy {
  min-width: 0;
}
.mount-perm-name {
  display: block;
  overflow: hidden;
  color: var(--text-regular);
  font-size: 13px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mount-perm-type {
  display: block;
  margin-top: 3px;
  color: var(--text-secondary);
  font-size: 12px;
}
.qos-form {
  display: grid;
  grid-template-columns: repeat(3, minmax(150px, 1fr));
  gap: 12px;
}
.qos-form :deep(.el-form-item) {
  margin-bottom: 0;
}
.qos-form :deep(.el-input-number) {
  width: 100%;
}
.role-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
}
.mobile-actions {
  display: none;
}

@media (max-width: 768px) {
  .role-permission {
    padding: 14px;
  }
  .permission-header {
    display: block;
  }
  .desktop-actions {
    display: none;
  }
  .mobile-actions {
    display: flex;
  }
  .mount-perm-row,
  .qos-form {
    grid-template-columns: 1fr;
  }
  .mount-perm-row :deep(.el-radio-group) {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    width: 100%;
  }
  .mount-perm-row :deep(.el-radio-button__inner) {
    width: 100%;
    padding-left: 8px;
    padding-right: 8px;
  }
  .role-actions :deep(.el-button) {
    flex: 1 1 0;
  }
}

@media (max-width: 480px) {
  .perm-grid {
    grid-template-columns: 1fr;
  }
  .mount-perm-row :deep(.el-radio-group) {
    grid-template-columns: 1fr;
  }
  .mount-perm-row :deep(.el-radio-button__inner) {
    border-left: var(--el-border);
    border-radius: 0;
  }
  .mount-perm-row :deep(.el-radio-button:first-child .el-radio-button__inner) {
    border-radius: var(--el-border-radius-base) var(--el-border-radius-base) 0 0;
  }
  .mount-perm-row :deep(.el-radio-button:last-child .el-radio-button__inner) {
    border-radius: 0 0 var(--el-border-radius-base) var(--el-border-radius-base);
  }
}
</style>
