import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import {
  archiveNotification,
  deleteNotification,
  getNotifications,
  getNotificationTypes,
  getUnreadCount,
  markRead,
  markAllRead,
} from '@/api/notifications'

export const useNotificationsStore = defineStore('notifications', () => {
  const notifications = ref([])
  const unreadCount = ref(0)
  const loading = ref(false)
  const loadingMore = ref(false)
  const total = ref(0)
  const hasMore = ref(false)
  const typeOptions = ref([])
  const filters = reactive({
    unreadOnly: false,
    type: '',
    pendingOnly: false,
    includeArchived: false,
    page: 1,
    pageSize: 20,
  })

  function isPendingActionable(notification) {
    return notification.type === 'access_request'
      && notification.metadata?.requester_id
      && !notification.metadata?.action_status
  }

  function matchesCurrentFilters(notification) {
    if (!filters.includeArchived && notification.is_archived) return false
    if (filters.unreadOnly && notification.is_read) return false
    if (filters.type && notification.type !== filters.type) return false
    if (filters.pendingOnly && !isPendingActionable(notification)) return false
    return true
  }

  function upsertNotification(notification) {
    const index = notifications.value.findIndex((n) => n.id === notification.id)
    if (index === -1) {
      notifications.value.unshift(notification)
      return true
    } else {
      notifications.value[index] = { ...notifications.value[index], ...notification }
      return false
    }
  }

  function removeNotification(id) {
    notifications.value = notifications.value.filter((n) => n.id !== id)
  }

  function applyResponse(data, replace) {
    const items = data?.items || []
    if (replace) {
      notifications.value = items
    } else {
      for (const item of items) {
        const index = notifications.value.findIndex((n) => n.id === item.id)
        if (index === -1) notifications.value.push(item)
        else notifications.value[index] = { ...notifications.value[index], ...item }
      }
    }
    total.value = data?.total || 0
    filters.page = data?.page || filters.page
    filters.pageSize = data?.page_size || filters.pageSize
    hasMore.value = Boolean(data?.has_more)
  }

  function normalizeFetchOptions(options) {
    if (typeof options === 'boolean') return { unreadOnly: options }
    return options || {}
  }

  async function fetchNotificationTypes() {
    const data = await getNotificationTypes({ include_archived: filters.includeArchived })
    typeOptions.value = data.types || []
  }

  async function fetchNotifications(options = {}) {
    const next = normalizeFetchOptions(options)
    Object.assign(filters, {
      unreadOnly: Boolean(next.unreadOnly ?? filters.unreadOnly),
      type: next.type ?? filters.type,
      pendingOnly: Boolean(next.pendingOnly ?? filters.pendingOnly),
      includeArchived: Boolean(next.includeArchived ?? filters.includeArchived),
      page: 1,
      pageSize: next.pageSize ?? filters.pageSize,
    })
    loading.value = true
    try {
      const data = await getNotifications({
        unread_only: filters.unreadOnly,
        type: filters.type || undefined,
        pending_only: filters.pendingOnly,
        include_archived: filters.includeArchived,
        page: filters.page,
        page_size: filters.pageSize,
      })
      applyResponse(data, true)
      await fetchNotificationTypes()
    } finally {
      loading.value = false
    }
  }

  async function loadMoreNotifications() {
    if (!hasMore.value || loadingMore.value) return
    loadingMore.value = true
    try {
      const data = await getNotifications({
        unread_only: filters.unreadOnly,
        type: filters.type || undefined,
        pending_only: filters.pendingOnly,
        include_archived: filters.includeArchived,
        page: filters.page + 1,
        page_size: filters.pageSize,
      })
      applyResponse(data, false)
    } finally {
      loadingMore.value = false
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
    const data = await markRead(id)
    const notif = notifications.value.find((n) => n.id === id)
    if (notif) {
      notif.is_read = true
      if (!matchesCurrentFilters(notif)) removeNotification(id)
    }
    if (typeof data?.unread_count === 'number') {
      unreadCount.value = data.unread_count
    }
  }

  async function markAllNotificationsRead() {
    const data = await markAllRead()
    notifications.value.forEach((n) => { n.is_read = true })
    if (filters.unreadOnly) notifications.value = []
    unreadCount.value = typeof data?.unread_count === 'number' ? data.unread_count : 0
  }

  async function archiveOne(id) {
    const data = await archiveNotification(id)
    const notif = notifications.value.find((n) => n.id === id)
    if (notif) {
      notif.is_read = true
      notif.is_archived = true
    }
    if (!filters.includeArchived) removeNotification(id)
    if (typeof data?.unread_count === 'number') unreadCount.value = data.unread_count
  }

  async function deleteOne(id) {
    const data = await deleteNotification(id)
    removeNotification(id)
    if (typeof data?.unread_count === 'number') unreadCount.value = data.unread_count
  }

  function handleWsMessage(data) {
    if (data.type === 'notification_new') {
      const matches = matchesCurrentFilters(data.notification)
      const inserted = matches ? upsertNotification(data.notification) : true
      if (inserted && !data.notification.is_read) unreadCount.value++
    } else if (data.type === 'notification_update') {
      if (matchesCurrentFilters(data.notification)) upsertNotification(data.notification)
      else removeNotification(data.notification.id)
    } else if (data.type === 'notification_delete') {
      removeNotification(data.notification_id)
    } else if (data.type === 'notification_count') {
      unreadCount.value = data.unread_count
    }
  }

  return {
    notifications,
    unreadCount,
    loading,
    loadingMore,
    total,
    hasMore,
    typeOptions,
    filters,
    fetchNotifications,
    loadMoreNotifications,
    fetchNotificationTypes,
    fetchUnreadCount,
    markNotificationRead,
    markAllNotificationsRead,
    archiveOne,
    deleteOne,
    handleWsMessage,
    upsertNotification,
  }
})
