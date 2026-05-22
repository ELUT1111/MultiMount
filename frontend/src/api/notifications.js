import request from '@/utils/request'

export const getNotifications = (params) => request.get('/notifications', { params })

export const getNotificationTypes = (params) => request.get('/notifications/types', { params })

export const getUnreadCount = () => request.get('/notifications/unread-count')

export const markRead = (id) => request.put(`/notifications/${id}/read`)

export const markAllRead = () => request.put('/notifications/read-all')

export const archiveNotification = (id) => request.put(`/notifications/${id}/archive`)

export const deleteNotification = (id) => request.delete(`/notifications/${id}`)

export const handleNotificationAction = (id, action) => request.post(`/notifications/${id}/action`, { action })
