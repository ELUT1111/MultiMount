<!--
  主布局壳 — 顶部导航栏 + 左侧侧边栏 + 中间主内容区 (router-view)。
-->
<template>
  <div class="layout">
    <TopNavbar />
    <div class="layout-body">
      <SidePanel />
      <main class="layout-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import TopNavbar from '@/components/layout/TopNavbar.vue'
import SidePanel from '@/components/layout/SidePanel.vue'
</script>

<style scoped>
.layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.layout-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.layout-main {
  flex: 1;
  padding: 16px;
  overflow: auto;
  background: var(--bg-color);
}
</style>
