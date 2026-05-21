<template>
  <div class="thumbnail" :class="{ empty: !url }">
    <img v-if="url" :src="url" :alt="file?.name || ''" @error="failed = true" />
    <el-icon v-else-if="file?.is_dir" :size="40" color="var(--primary-color)"><Folder /></el-icon>
    <el-icon v-else :size="40"><Document /></el-icon>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { Document, Folder } from '@element-plus/icons-vue'
import { getThumbnailUrl } from '@/api/files'

const props = defineProps({
  mountId: { type: Number, default: null },
  file: { type: Object, default: null },
})

const url = ref('')
const failed = ref(false)

function cleanup() {
  if (url.value) URL.revokeObjectURL(url.value)
  url.value = ''
  failed.value = false
}

function authHeaders() {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

watch(
  () => [props.mountId, props.file?.path, props.file?.modified_at],
  async () => {
    cleanup()
    if (!props.mountId || !props.file || props.file.is_dir) return
    try {
      const resp = await fetch(getThumbnailUrl(props.mountId, props.file.path), { headers: authHeaders() })
      if (!resp.ok) throw new Error('thumbnail failed')
      url.value = URL.createObjectURL(await resp.blob())
    } catch {
      failed.value = true
    }
  },
  { immediate: true }
)

onBeforeUnmount(cleanup)
</script>

<style scoped>
.thumbnail {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  overflow: hidden;
  background: #f5f7fa;
}
.thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumbnail.empty {
  background: transparent;
}
</style>
