import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './styles/global.css'
import { useAppStore } from './stores/app'

async function applyHttpsRedirectPolicy() {
  if (window.location.protocol !== 'http:') return

  const apiOrigin = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') || ''
  try {
    const response = await fetch(`${apiOrigin}/api/v1/system/https/redirect-policy`, {
      credentials: 'include',
    })
    if (!response.ok) return

    const policy = await response.json()
    if (!policy.redirect_enabled) return

    const target = new URL(window.location.href)
    target.protocol = 'https:'
    window.location.replace(target.toString())
  } catch {
    // 保持 HTTP 可访问, 避免策略接口不可用时阻塞应用启动。
  }
}

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })

useAppStore().applyPreferences()

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

applyHttpsRedirectPolicy().finally(() => {
  app.mount('#app')
})
