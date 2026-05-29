<!--
  登录/注册页面 — 支持登录和注册两种模式切换。
-->
<template>
  <div class="login-page">
    <div class="login-shell">
      <section class="brand-stage" aria-hidden="true">
        <div class="stage-grid" />
        <div class="brand-copy">
          <div class="brand-mark">
            <el-icon><Connection /></el-icon>
          </div>
          <div>
            <h1>MultiMount</h1>
            <p>把分散的文件协议汇入一个清晰入口</p>
          </div>
        </div>

        <div class="mount-orbit">
          <div class="orbit-ring ring-one" />
          <div class="orbit-ring ring-two" />
          <div class="hub-node">
            <el-icon><FolderOpened /></el-icon>
            <span>Unified Hub</span>
          </div>
          <div class="protocol-node node-local">
            <el-icon><FolderOpened /></el-icon>
            <span>Local</span>
          </div>
          <div class="protocol-node node-ftp">
            <el-icon><Connection /></el-icon>
            <span>FTP</span>
          </div>
          <div class="protocol-node node-webdav">
            <el-icon><Monitor /></el-icon>
            <span>WebDAV</span>
          </div>
          <div class="protocol-node node-cloud">
            <el-icon><Cloudy /></el-icon>
            <span>S3 / OSS</span>
          </div>
        </div>

        <div class="stage-metrics">
          <div>
            <strong>6</strong>
            <span>协议源</span>
          </div>
          <div>
            <strong>ACL</strong>
            <span>权限控制</span>
          </div>
          <div>
            <strong>Live</strong>
            <span>连接监测</span>
          </div>
        </div>
      </section>

      <section class="auth-panel">
        <div class="auth-header">
          <div class="mobile-brand">
            <span class="mobile-logo"><el-icon><Connection /></el-icon></span>
            <span>MultiMount</span>
          </div>
          <p class="auth-eyebrow">Secure Workspace</p>
          <h2>{{ mode === 'login' ? '登录控制台' : '创建工作账号' }}</h2>
          <p>{{ mode === 'login' ? '集中访问你的挂载源、分享链接和传输任务。' : '注册后即可添加挂载源并管理访问权限。' }}</p>
        </div>

        <div class="mode-switch" role="tablist" aria-label="登录注册切换">
          <button type="button" :class="{ active: mode === 'login' }" @click="switchMode('login')">登录</button>
          <button type="button" :class="{ active: mode === 'register' }" @click="switchMode('register')">注册</button>
        </div>

        <transition name="fade" mode="out-in">
          <el-form v-if="mode === 'login'" key="login" ref="loginFormRef" class="auth-form" :model="loginForm" :rules="loginRules" label-width="0" size="large" aria-label="登录表单">
            <el-form-item prop="login_id">
              <el-input v-model="loginForm.login_id" placeholder="账号、用户名或邮箱" :prefix-icon="User" :disabled="loading" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="loginForm.password" type="password" placeholder="密码" :prefix-icon="Lock" show-password :disabled="loading" @keyup.enter="handleLogin" />
            </el-form-item>
            <el-form-item>
              <el-button class="primary-action" type="primary" :loading="loading" @click="handleLogin">登录 MultiMount</el-button>
            </el-form-item>
            <div class="form-footer">
              <span>还没有账号?</span>
              <el-link type="primary" @click="switchMode('register')">立即注册</el-link>
            </div>
          </el-form>

          <el-form v-else key="register" ref="registerFormRef" class="auth-form" :model="registerForm" :rules="registerRules" label-width="0" size="large" aria-label="注册表单">
            <el-form-item prop="account">
              <el-input v-model="registerForm.account" placeholder="账号 (2-64字符, 不可修改)" :prefix-icon="User" :disabled="loading" />
            </el-form-item>
            <el-form-item prop="username">
              <el-input v-model="registerForm.username" placeholder="用户名 (2-64字符)" :prefix-icon="User" :disabled="loading" />
            </el-form-item>
            <el-form-item prop="email">
              <el-input v-model="registerForm.email" placeholder="邮箱地址" :prefix-icon="Message" :disabled="loading" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="registerForm.password" type="password" placeholder="密码 (至少6位)" :prefix-icon="Lock" show-password :disabled="loading" />
            </el-form-item>
            <el-form-item prop="confirmPassword">
              <el-input v-model="registerForm.confirmPassword" type="password" placeholder="确认密码" :prefix-icon="Lock" show-password :disabled="loading" @keyup.enter="handleRegister" />
            </el-form-item>
            <el-form-item>
              <el-button class="primary-action" type="primary" :loading="loading" @click="handleRegister">创建账号</el-button>
            </el-form-item>
            <div class="form-footer">
              <span>已有账号?</span>
              <el-link type="primary" @click="switchMode('login')">返回登录</el-link>
            </div>
          </el-form>
        </transition>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, Message, Connection, FolderOpened, Monitor, Cloudy } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { register } from '@/api/auth'

const router = useRouter()
const auth = useAuthStore()
const loginFormRef = ref()
const registerFormRef = ref()
const loading = ref(false)
const mode = ref('login')

// 登录
const loginForm = reactive({ login_id: '', password: '' })
const loginRules = {
  login_id: [{ required: true, message: '请输入账号、用户名或邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  const valid = await loginFormRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.login(loginForm.login_id, loginForm.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

// 注册
const registerForm = reactive({ account: '', username: '', email: '', password: '', confirmPassword: '' })

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const registerRules = {
  account: [
    { required: true, message: '请输入账号', trigger: 'blur' },
    { min: 2, max: 64, message: '账号长度为 2-64 个字符', trigger: 'blur' },
  ],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 64, message: '用户名长度为 2-64 个字符', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 128, message: '密码长度至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

async function handleRegister() {
  const valid = await registerFormRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await register({
      account: registerForm.account,
      username: registerForm.username,
      email: registerForm.email,
      password: registerForm.password,
    })
    ElMessage.success('注册成功, 请登录')
    mode.value = 'login'
    loginForm.login_id = registerForm.account
    loginForm.password = ''
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}

function switchMode(m) {
  mode.value = m
  // 清除表单验证状态
  loginFormRef.value?.resetFields()
  registerFormRef.value?.resetFields()
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  overflow: hidden;
  background:
    radial-gradient(circle at 18% 20%, rgba(25, 118, 210, 0.22), transparent 30%),
    radial-gradient(circle at 82% 18%, rgba(34, 197, 94, 0.18), transparent 28%),
    linear-gradient(135deg, #eef5ff 0%, #f7fbff 48%, #ecfdf5 100%);
}

.login-shell {
  width: min(1080px, 100%);
  min-height: 680px;
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(380px, 0.82fr);
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 24px;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.18);
  backdrop-filter: blur(18px);
  overflow: hidden;
}

.brand-stage {
  position: relative;
  min-height: 680px;
  padding: 40px;
  color: #fff;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(15, 76, 129, 0.96), rgba(16, 112, 118, 0.92)),
    #12385f;
}

.stage-grid {
  position: absolute;
  inset: 0;
  opacity: 0.26;
  background-image:
    linear-gradient(rgba(255,255,255,0.16) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.16) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: radial-gradient(circle at center, black 0%, transparent 76%);
}

.brand-stage::before,
.brand-stage::after {
  content: "";
  position: absolute;
  width: 360px;
  height: 360px;
  border-radius: 50%;
  filter: blur(12px);
  opacity: 0.22;
  animation: float-blob 8s ease-in-out infinite;
}

.brand-stage::before {
  left: -120px;
  top: 80px;
  background: #7dd3fc;
}

.brand-stage::after {
  right: -140px;
  bottom: -80px;
  background: #86efac;
  animation-delay: -3s;
}

.brand-copy {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 16px;
}

.brand-mark,
.mobile-logo {
  width: 52px;
  height: 52px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: rgba(255,255,255,0.16);
  border: 1px solid rgba(255,255,255,0.28);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08);
}

.brand-copy h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.1;
  letter-spacing: 0;
}

.brand-copy p {
  margin: 8px 0 0;
  color: rgba(255,255,255,0.76);
  font-size: 14px;
}

.mount-orbit {
  position: absolute;
  inset: 110px 44px 112px;
  z-index: 1;
}

.orbit-ring {
  position: absolute;
  inset: 14%;
  border: 1px solid rgba(255,255,255,0.24);
  border-radius: 50%;
  animation: orbit-spin 24s linear infinite;
}

.ring-two {
  inset: 24%;
  border-style: dashed;
  animation-duration: 18s;
  animation-direction: reverse;
}

.hub-node,
.protocol-node {
  position: absolute;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.26);
  background: rgba(7, 27, 46, 0.48);
  box-shadow: 0 16px 42px rgba(0,0,0,0.22), inset 0 0 0 1px rgba(255,255,255,0.08);
  backdrop-filter: blur(12px);
}

.hub-node {
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  padding: 18px 20px;
  font-size: 16px;
  font-weight: 700;
  background: rgba(255,255,255,0.18);
}

.protocol-node {
  padding: 12px 14px;
  font-size: 13px;
  color: rgba(255,255,255,0.9);
  animation: node-float 5.5s ease-in-out infinite;
}

.node-local { left: 8%; top: 18%; }
.node-ftp { right: 8%; top: 28%; animation-delay: -1.1s; }
.node-webdav { left: 14%; bottom: 18%; animation-delay: -2.2s; }
.node-cloud { right: 10%; bottom: 16%; animation-delay: -3.2s; }

.stage-metrics {
  position: absolute;
  z-index: 2;
  left: 40px;
  right: 40px;
  bottom: 36px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.stage-metrics div {
  padding: 14px;
  border-radius: 16px;
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.18);
}

.stage-metrics strong {
  display: block;
  font-size: 18px;
  line-height: 1.2;
}

.stage-metrics span {
  display: block;
  margin-top: 4px;
  color: rgba(255,255,255,0.68);
  font-size: 12px;
}

.auth-panel {
  position: relative;
  z-index: 3;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 46px;
  background: rgba(255,255,255,0.9);
}

.auth-header {
  margin-bottom: 22px;
}

.mobile-brand {
  display: none;
}

.auth-eyebrow {
  margin: 0 0 10px;
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.auth-header h2 {
  margin: 0;
  color: #102033;
  font-size: 32px;
  line-height: 1.18;
  letter-spacing: 0;
}

.auth-header > p:last-child {
  margin: 10px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.7;
}

.mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 6px;
  margin-bottom: 22px;
  border-radius: 12px;
  background: #edf4fb;
}

.mode-switch button {
  height: 40px;
  border: 0;
  border-radius: 9px;
  color: #64748b;
  background: transparent;
  font-weight: 700;
  cursor: pointer;
  transition: color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}

.mode-switch button.active {
  color: #0f172a;
  background: #fff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
}

.auth-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.auth-form :deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 12px;
  box-shadow: 0 0 0 1px #d9e5f2 inset;
  background: #f8fbff;
  transition: box-shadow 0.2s ease, background 0.2s ease;
}

.auth-form :deep(.el-input__wrapper.is-focus) {
  background: #fff;
  box-shadow: 0 0 0 1px #0ea5e9 inset, 0 0 0 4px rgba(14,165,233,0.12);
}

.primary-action {
  width: 100%;
  height: 48px;
  border: 0;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 800;
  background: linear-gradient(135deg, #0ea5e9 0%, #0f766e 100%);
  box-shadow: 0 14px 30px rgba(14, 116, 144, 0.28);
}

.primary-action:hover {
  filter: saturate(1.08);
  transform: translateY(-1px);
}

.form-footer {
  text-align: center;
  margin-top: -2px;
  font-size: 13px;
  color: #64748b;
  display: flex;
  justify-content: center;
  gap: 6px;
}

/* 表单切换过渡 */
.fade-enter-active, .fade-leave-active { transition: opacity 0.24s ease, transform 0.24s ease; }
.fade-enter-from { opacity: 0; transform: translateY(12px); }
.fade-leave-to { opacity: 0; transform: translateY(-12px); }

@keyframes node-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

@keyframes orbit-spin {
  to { transform: rotate(360deg); }
}

@keyframes float-blob {
  0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
  50% { transform: translate3d(18px, -14px, 0) scale(1.04); }
}

/* 深色主题 */
.dark .login-page {
  background:
    radial-gradient(circle at 18% 20%, rgba(14, 165, 233, 0.18), transparent 30%),
    radial-gradient(circle at 82% 18%, rgba(20, 184, 166, 0.16), transparent 28%),
    linear-gradient(135deg, #07111f 0%, #0f172a 100%);
}
.dark .login-shell {
  background: rgba(15,23,42,0.72);
  border-color: rgba(148,163,184,0.18);
}
.dark .auth-panel {
  background: rgba(15,23,42,0.92);
}
.dark .auth-header h2 {
  color: #f8fafc;
}
.dark .auth-header > p:last-child,
.dark .form-footer {
  color: #94a3b8;
}
.dark .mode-switch {
  background: #111c2d;
}
.dark .mode-switch button.active {
  color: #f8fafc;
  background: #1e293b;
}
.dark .auth-form :deep(.el-input__wrapper) {
  background: #111c2d;
  box-shadow: 0 0 0 1px #334155 inset;
}
.dark .auth-form :deep(.el-input__wrapper.is-focus) {
  background: #0f172a;
  box-shadow: 0 0 0 1px #38bdf8 inset, 0 0 0 4px rgba(56,189,248,0.12);
}

@media (max-width: 900px) {
  .login-page {
    align-items: stretch;
    padding: 16px;
    overflow: auto;
  }
  .login-shell {
    min-height: auto;
    grid-template-columns: 1fr;
    border-radius: 18px;
  }
  .brand-stage {
    display: none;
  }
  .auth-panel {
    min-height: calc(100vh - 32px);
    padding: 28px 22px;
  }
  .mobile-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 18px;
    color: #0f766e;
    font-weight: 800;
  }
  .mobile-logo {
    width: 38px;
    height: 38px;
    border-radius: 12px;
    color: #0f766e;
    background: #e6fffb;
    border-color: #b5f5ec;
  }
  .auth-header h2 {
    font-size: 28px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .brand-stage::before,
  .brand-stage::after,
  .orbit-ring,
  .protocol-node {
    animation: none;
  }
  .fade-enter-active,
  .fade-leave-active,
  .card-action,
  .primary-action,
  .mode-switch button,
  .auth-form :deep(.el-input__wrapper) {
    transition: none;
  }
}
</style>
