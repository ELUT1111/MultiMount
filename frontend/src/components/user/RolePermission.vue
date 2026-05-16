<!--
  角色权限配置组件 — 基础权限勾选、挂载点权限设置、QoS 速率限制。
-->
<template>
  <div v-if="role" class="role-permission">
    <h3>{{ role.name }} - 权限配置</h3>
    <el-divider />

    <!-- 基础权限 -->
    <h4>基础权限</h4>
    <div class="perm-grid">
      <el-checkbox v-model="localRole.permissions.can_login" label="允许登录" />
      <el-checkbox v-model="localRole.permissions.can_upload" label="允许上传" />
      <el-checkbox v-model="localRole.permissions.can_download" label="允许下载" />
      <el-checkbox v-model="localRole.permissions.can_modify" label="允许修改" />
      <el-checkbox v-model="localRole.permissions.can_delete" label="允许删除" />
      <el-checkbox v-model="localRole.permissions.can_manage_mounts" label="允许挂载管理" />
    </div>

    <el-divider />

    <!-- 挂载点权限 -->
    <h4>挂载点权限</h4>
    <div class="mount-perms">
      <div v-for="mount in mounts" :key="mount.id" class="mount-perm-row">
        <span class="mount-perm-name">{{ mount.name }}</span>
        <el-radio-group v-model="localRole.mount_permissions[mount.id]" size="small">
          <el-radio-button label="none">不可见</el-radio-button>
          <el-radio-button label="read">只读</el-radio-button>
          <el-radio-button label="readwrite">读写</el-radio-button>
        </el-radio-group>
      </div>
      <el-empty v-if="mounts.length === 0" description="暂无挂载点" :image-size="40" />
    </div>

    <el-divider />

    <!-- QoS 速率限制 -->
    <h4>QoS 速率限制</h4>
    <el-form label-width="160px" style="max-width:400px">
      <el-form-item label="最大下载速率(KB/s)">
        <el-input-number v-model="localRole.qos_limits.max_download_kbps" :min="0" />
      </el-form-item>
      <el-form-item label="最大上传速率(KB/s)">
        <el-input-number v-model="localRole.qos_limits.max_upload_kbps" :min="0" />
      </el-form-item>
      <el-form-item label="最大并发连接数">
        <el-input-number v-model="localRole.qos_limits.max_concurrent" :min="1" />
      </el-form-item>
    </el-form>

    <div class="role-actions">
      <el-button type="primary" @click="$emit('save', localRole)">保存配置</el-button>
      <el-button @click="$emit('reset')">重置</el-button>
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
.role-permission { padding: 16px; }
.role-permission.empty { display: flex; align-items: center; justify-content: center; min-height: 300px; }
.role-permission h3 { font-size: 16px; margin: 0; }
.role-permission h4 { font-size: 14px; color: var(--text-secondary); margin: 8px 0; }
.perm-grid { display: flex; flex-wrap: wrap; gap: 16px; margin: 12px 0; }
.mount-perms { display: flex; flex-direction: column; gap: 10px; margin: 12px 0; }
.mount-perm-row { display: flex; align-items: center; gap: 12px; }
.mount-perm-name { min-width: 120px; font-size: 13px; color: var(--text-regular); }
.role-actions { display: flex; gap: 8px; margin-top: 16px; }
</style>
