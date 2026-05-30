<template>
  <div class="batch-toolbar">
    <span class="batch-summary">{{ summary }}</span>
    <div class="batch-actions">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  summary: { type: String, required: true },
})
</script>

<style scoped>
.batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(64, 158, 255, 0.08);
  border: 1px solid rgba(64, 158, 255, 0.18);
  color: var(--text-regular);
  font-size: 13px;
}

.batch-summary {
  min-width: 0;
  font-weight: 600;
}

.batch-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .batch-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .batch-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .batch-actions :deep(.el-button) {
    flex: 1 1 120px;
  }
}
</style>
