import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/files' },
      {
        path: 'files',
        name: 'FileBrowser',
        component: () => import('@/views/FileBrowser.vue'),
      },
      {
        path: 'mounts',
        name: 'MountManager',
        component: () => import('@/views/MountManager.vue'),
      },
      {
        path: 'users',
        name: 'UserManager',
        component: () => import('@/views/UserManager.vue'),
        meta: { requiresAdmin: true },
      },
      {
        path: 'profile',
        name: 'PersonalSettings',
        component: () => import('@/views/PersonalSettings.vue'),
      },
      {
        path: 'transfers',
        name: 'TransferTasks',
        component: () => import('@/views/TransferTasks.vue'),
      },
      {
        path: 'settings',
        name: 'SystemSettings',
        component: () => import('@/views/SystemSettings.vue'),
        meta: { requiresAdmin: true },
      },
      {
        path: 'monitor',
        name: 'RequestMonitor',
        component: () => import('@/views/RequestMonitor.vue'),
        meta: { requiresAdmin: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 导航守卫: 校验 JWT + 管理员权限
router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth !== false && !auth.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && auth.isAuthenticated) {
    next('/')
  } else if (to.meta.requiresAdmin && !auth.isAdmin) {
    next('/files')
  } else {
    next()
  }
})

export default router
