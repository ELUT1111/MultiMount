<template>
  <section class="unified-state" :class="`state-${type}`" role="status" :aria-label="title || description">
    <el-icon class="state-icon" :size="42">
      <component :is="iconComponent" />
    </el-icon>
    <div class="state-copy">
      <h3 v-if="title">{{ title }}</h3>
      <p>{{ description }}</p>
    </div>
    <div v-if="$slots.actions || actionText" class="state-actions">
      <slot name="actions">
        <el-button v-if="actionText" type="primary" @click="$emit('action')">{{ actionText }}</el-button>
      </slot>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { CircleClose, FolderOpened, InfoFilled, Lock, Search, Warning } from '@element-plus/icons-vue'

const props = defineProps({
  type: { type: String, default: 'empty' },
  title: { type: String, default: '' },
  description: { type: String, required: true },
  actionText: { type: String, default: '' },
})

defineEmits(['action'])

const iconComponent = computed(() => ({
  empty: FolderOpened,
  error: CircleClose,
  offline: Warning,
  forbidden: Lock,
  search: Search,
  info: InfoFilled,
})[props.type] || InfoFilled)
</script>

<style scoped>
.unified-state {
  min-height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 32px 20px;
  color: var(--text-secondary);
  text-align: center;
}
.state-icon { color: var(--state-color, var(--text-secondary)); }
.state-error { --state-color: var(--danger-color); }
.state-offline { --state-color: var(--warning-color); }
.state-forbidden { --state-color: var(--danger-color); }
.state-search { --state-color: var(--primary-color); }
.state-copy h3 {
  margin: 0 0 4px;
  font-size: 16px;
  color: var(--text-primary);
}
.state-copy p {
  margin: 0;
  max-width: 420px;
  line-height: 1.6;
}
.state-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 4px;
}
</style>
