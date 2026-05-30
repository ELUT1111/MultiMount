<!--
  个人设置页面 — 修改用户名、邮箱、密码。account 只读。
-->
<template>
  <div class="personal-settings">
    <h2>个人设置</h2>

    <!-- 基本信息 -->
    <div class="settings-section">
      <div class="section-title">基本信息</div>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px" style="max-width: 480px">
        <el-form-item label="账号">
          <el-input :model-value="auth.user?.account" disabled />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="用户名" @blur="checkUsernameUnique" />
          <div v-if="usernameStatus === 'checking'" class="unique-hint checking">检查中...</div>
          <div v-else-if="usernameStatus === 'taken'" class="unique-hint taken">用户名已被使用</div>
          <div v-else-if="usernameStatus === 'available'" class="unique-hint available">用户名可用</div>
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="邮箱地址" @blur="checkEmailUnique" />
          <div v-if="emailStatus === 'checking'" class="unique-hint checking">检查中...</div>
          <div v-else-if="emailStatus === 'taken'" class="unique-hint taken">邮箱已被使用</div>
          <div v-else-if="emailStatus === 'available'" class="unique-hint available">邮箱可用</div>
        </el-form-item>
      </el-form>
    </div>

    <!-- 修改密码 -->
    <div class="settings-section">
      <div class="section-title">修改密码</div>
      <el-form :model="pwForm" :rules="pwRules" ref="pwFormRef" label-width="100px" style="max-width: 480px">
        <el-form-item label="当前密码" prop="current_password">
          <el-input v-model="pwForm.current_password" type="password" show-password placeholder="修改密码时必填" />
        </el-form-item>
        <el-form-item label="新密码" prop="password">
          <el-input v-model="pwForm.password" type="password" show-password placeholder="至少6位" />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input v-model="pwForm.confirm_password" type="password" show-password placeholder="再次输入新密码" />
        </el-form-item>
      </el-form>
    </div>

    <!-- 保存按钮 -->
    <div class="settings-actions">
      <el-button type="primary" :loading="saving" @click="handleSave">保存修改</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { updateMe, checkUnique } from '@/api/users'

const auth = useAuthStore()
const formRef = ref()
const pwFormRef = ref()
const saving = ref(false)

const form = reactive({ username: '', email: '' })
const pwForm = reactive({ current_password: '', password: '', confirm_password: '' })

const usernameStatus = ref('') // '' | 'checking' | 'available' | 'taken'
const emailStatus = ref('')

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 64, message: '用户名长度为 2-64 个字符', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' },
  ],
}

const validateConfirmPassword = (_rule, value, callback) => {
  if (pwForm.password && value !== pwForm.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const pwRules = {
  current_password: [
    { required: true, message: '请输入当前密码', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 128, message: '密码长度至少 6 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

async function checkUsernameUnique() {
  if (!form.username || form.username === auth.user?.username) {
    usernameStatus.value = ''
    return
  }
  usernameStatus.value = 'checking'
  try {
    const res = await checkUnique('username', form.username)
    usernameStatus.value = res.available ? 'available' : 'taken'
  } catch {
    usernameStatus.value = ''
  }
}

async function checkEmailUnique() {
  if (!form.email || form.email === auth.user?.email) {
    emailStatus.value = ''
    return
  }
  emailStatus.value = 'checking'
  try {
    const res = await checkUnique('email', form.email)
    emailStatus.value = res.available ? 'available' : 'taken'
  } catch {
    emailStatus.value = ''
  }
}

async function handleSave() {
  // 验证基本信息表单
  const formValid = await formRef.value.validate().catch(() => false)

  // 如果要改密码，验证密码表单
  const hasPasswordChange = pwForm.password || pwForm.current_password || pwForm.confirm_password
  let pwValid = true
  if (hasPasswordChange) {
    pwValid = await pwFormRef.value.validate().catch(() => false)
  }

  if (!formValid || !pwValid) return

  // 检查唯一性状态
  if (usernameStatus.value === 'taken' || emailStatus.value === 'taken') {
    ElMessage.error('请修正重复的字段后再保存')
    return
  }

  saving.value = true
  try {
    const payload = {}
    if (form.username !== auth.user?.username) payload.username = form.username
    if (form.email !== auth.user?.email) payload.email = form.email
    if (hasPasswordChange) {
      payload.current_password = pwForm.current_password
      payload.password = pwForm.password
    }

    if (Object.keys(payload).length === 0) {
      ElMessage.info('未做任何修改')
      saving.value = false
      return
    }

    const updated = await updateMe(payload)
    // 更新 auth store 中的用户信息
    auth.user = { ...auth.user, ...updated }
    localStorage.setItem('user', JSON.stringify(auth.user))
    ElMessage.success('保存成功')

    // 清空密码表单
    pwForm.current_password = ''
    pwForm.password = ''
    pwForm.confirm_password = ''
    usernameStatus.value = ''
    emailStatus.value = ''
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  if (auth.user) {
    form.username = auth.user.username || ''
    form.email = auth.user.email || ''
  }
})
</script>

<style scoped>
.personal-settings {
  max-width: 640px;
  margin: 0 auto;
  padding: 24px;
}
.personal-settings h2 {
  font-size: 20px;
  margin-bottom: 24px;
}
.settings-section {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 1px 4px color-mix(in srgb, var(--text-primary) 8%, transparent);
  border: 1px solid var(--border-color);
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--text-primary);
}
.settings-actions {
  text-align: right;
}
.unique-hint {
  font-size: 12px;
  margin-top: 4px;
  line-height: 1;
}
.unique-hint.checking { color: var(--info-color); }
.unique-hint.taken { color: var(--danger-color); }
.unique-hint.available { color: var(--success-color); }
</style>
