import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getNotifications, getUnreadCount, markRead, markAllRead } from '@/api/notifications'

export const useNotificationsStore = defineStore('notifications', () => {
  const notifications = ref([])
  const unreadCount = ref(0)
  const loading = ref(false)

  async function fetchNotifications(unreadOnly = false) {
    loading.value = true
    try {
      notifications.value = await getNotifications({ unread_only: unreadOnly })
    } finally {
      loading.value = false
    }
  }

  async function fetchUnreadCount() {
    try {
      const data = await getUnreadCount()
      unreadCount.value = data.unread_count
    } catch {
      // 静默失败
    }
  }

  async function markNotificationRead(id) {
    await markRead(id)
    const notif = notifications.value.find((n) => n.id === id)
    if (notif) notif.is_read = true
    if (unreadCount.value > 0) unreadCount.value--
  }

  async function markAllNotificationsRead() {
    await markAllRead()
    notifications.value.forEach((n) => { n.is_read = true })
    unreadCount.value = 0
  }

  function handleWsMessage(data) {
    if (data.type === 'notification_new') {
      // 新通知插入到列表顶部
      notifications.value.unshift(data.notification)
      unreadCount.value++
    } else if (data.type === 'notification_count') {
      unreadCount.value = data.unread_count
    }
  }

  return {
    notifications,
    unreadCount,
    loading,
    fetchNotifications,
    fetchUnreadCount,
    markNotificationRead,
    markAllNotificationsRead,
    handleWsMessage,
  }
})
