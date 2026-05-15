<!--
  骨架屏加载组件 — 在数据加载期间显示占位动画。
  支持行数和头像模式配置。
-->
<template>
  <div class="skeleton-loader" :class="{ 'with-avatar': avatar }">
    <div v-if="avatar" class="skeleton-avatar" />
    <div class="skeleton-content">
      <div v-if="title" class="skeleton-title" :style="{ width: titleWidth }" />
      <div v-for="n in rows" :key="n" class="skeleton-text" :style="{ width: n === rows ? '60%' : '100%' }" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  rows: { type: Number, default: 3 },
  avatar: { type: Boolean, default: false },
  title: { type: Boolean, default: true },
  titleWidth: { type: String, default: '40%' },
})
</script>

<style scoped>
.skeleton-loader { display: flex; gap: 16px; padding: 16px; }
.skeleton-avatar {
  width: 48px; height: 48px; border-radius: 50%;
  background: var(--skeleton-bg, #e5e7eb);
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}
.skeleton-content { flex: 1; display: flex; flex-direction: column; gap: 12px; }
.skeleton-title {
  height: 20px; border-radius: 4px;
  background: var(--skeleton-bg, #e5e7eb);
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}
.skeleton-text {
  height: 14px; border-radius: 4px;
  background: var(--skeleton-bg, #e5e7eb);
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}
</style>
