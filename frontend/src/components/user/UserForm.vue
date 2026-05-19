<!--
  用户表单对话框 — 创建/编辑用户, 含用户名/邮箱/密码/角色字段。
-->
<template>
  <el-dialog :model-value="modelValue" :title="isEdit ? '编辑用户' : '添加用户'" class="responsive-dialog user-dialog"
    @update:model-value="$emit('update:modelValue', $event)" @close="resetForm">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item label="用户名" prop="username" required>
        <el-input v-model="form.username" :disabled="isEdit" placeholder="请输入用户名" />
      </el-form-item>
      <el-form-item label="邮箱" prop="email" required>
        <el-input v-model="form.email" placeholder="请输入邮箱" />
      </el-form-item>
      <el-form-item label="密码" :prop="isEdit ? '' : 'password'" :required="!isEdit">
        <el-input v-model="form.password" type="password" show-password :placeholder="isEdit ? '留空则不修改' : '请输入密码'" />
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="form.role_id" placeholder="选择角色" clearable style="width:100%">
          <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="handleSubmit">{{ isEdit ? '更新' : '创建' }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  editUser: { type: Object, default: null },
  roles: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'submit'])

const formRef = ref(null)
const form = reactive({ username: '', email: '', password: '', role_id: null })
const isEdit = ref(false)

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' },
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

watch(() => props.modelValue, (val) => {
  if (val && props.editUser) {
    isEdit.value = true
    form.username = props.editUser.username
    form.email = props.editUser.email
    form.password = ''
    form.role_id = props.editUser.role_id
  } else if (val) {
    isEdit.value = false
    resetForm()
  }
})

function resetForm() {
  form.username = ''
  form.email = ''
  form.password = ''
  form.role_id = null
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch { return }

  const payload = { ...form }
  if (isEdit.value && !payload.password) delete payload.password
  emit('submit', { isEdit: isEdit.value, userId: props.editUser?.id, payload })
}
</script>
