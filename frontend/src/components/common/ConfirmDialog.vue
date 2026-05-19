<!--
  确认对话框组件 — 封装 ElMessageBox.confirm, 提供统一的确认/取消交互。
  支持自定义标题、消息、类型和确认按钮文字。
-->
<template>
  <el-dialog v-model="visible" :title="title" class="responsive-dialog confirm-dialog" :close-on-click-modal="false">
    <div class="confirm-body">
      <el-icon :size="24" :color="iconColor" style="margin-right: 12px">
        <component :is="icon" />
      </el-icon>
      <span>{{ message }}</span>
    </div>
    <template #footer>
      <el-button @click="handleCancel">{{ cancelText }}</el-button>
      <el-button :type="type" @click="handleConfirm">{{ confirmText }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { WarningFilled, InfoFilled, SuccessFilled, CircleCloseFilled } from '@element-plus/icons-vue'

const props = defineProps({
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '确定要执行此操作吗?' },
  type: { type: String, default: 'primary', validator: (v) => ['primary', 'danger', 'warning', 'success'].includes(v) },
  confirmText: { type: String, default: '确定' },
  cancelText: { type: String, default: '取消' },
})

const emit = defineEmits(['confirm', 'cancel'])
const visible = ref(false)

const icon = computed(() => ({
  danger: CircleCloseFilled,
  warning: WarningFilled,
  success: SuccessFilled,
  primary: InfoFilled,
}[props.type] || InfoFilled))

const iconColor = computed(() => ({
  danger: '#f56c6c',
  warning: '#e6a23c',
  success: '#67c23a',
  primary: '#409eff',
}[props.type] || '#409eff'))

function open() { visible.value = true }
function handleConfirm() { visible.value = false; emit('confirm') }
function handleCancel() { visible.value = false; emit('cancel') }

defineExpose({ open })
</script>

<style scoped>
.confirm-body { display: flex; align-items: flex-start; padding: 12px 0; font-size: 14px; line-height: 1.6; }
</style>
