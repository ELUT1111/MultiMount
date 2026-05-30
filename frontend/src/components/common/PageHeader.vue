<template>
  <header class="page-header" :class="{ 'has-actions': hasActions }">
    <div class="header-copy">
      <p v-if="eyebrow" class="header-eyebrow">{{ eyebrow }}</p>
      <h2>{{ title }}</h2>
      <p v-if="description" class="header-description">{{ description }}</p>
      <div v-if="meta.length" class="header-meta">
        <span v-for="item in meta" :key="item">{{ item }}</span>
      </div>
    </div>
    <div v-if="hasActions" class="header-actions" :class="`layout-${actionsLayout}`">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup>
import { computed, useSlots } from 'vue'

defineProps({
  title: { type: String, required: true },
  eyebrow: { type: String, default: '' },
  description: { type: String, default: '' },
  meta: { type: Array, default: () => [] },
  actionsLayout: { type: String, default: 'grid' },
})

const slots = useSlots()
const hasActions = computed(() => Boolean(slots.actions))
</script>

<style scoped>
.page-header {
  display: grid;
  grid-template-columns: minmax(220px, 1fr);
  gap: 16px;
  align-items: end;
}

.page-header.has-actions {
  grid-template-columns: minmax(220px, 1fr) minmax(360px, max-content);
}

.header-copy {
  min-width: 0;
}

.header-eyebrow {
  margin: 0 0 6px;
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
}

.header-copy h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.25;
  letter-spacing: 0;
}

.header-description {
  max-width: 620px;
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.header-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}

.header-meta span {
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--card-bg);
  padding: 3px 10px;
}

.header-actions {
  min-width: 0;
}

.header-actions.layout-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  align-items: center;
  width: min(820px, 100%);
}

.header-actions.layout-flex {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.header-actions :deep(.el-input),
.header-actions :deep(.el-select),
.header-actions :deep(.el-button) {
  width: 100%;
  min-width: 0;
}

.header-actions.layout-flex :deep(.el-button) {
  width: auto;
}

@media (max-width: 1180px) {
  .page-header.has-actions {
    grid-template-columns: 1fr;
    align-items: start;
  }

  .header-actions.layout-grid {
    width: 100%;
  }

  .header-actions.layout-flex {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .page-header {
    gap: 12px;
  }

  .header-copy h2 {
    font-size: 20px;
  }

  .header-actions.layout-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 480px) {
  .header-actions.layout-grid {
    grid-template-columns: 1fr;
  }
}
</style>
