import request from '@/utils/request'

export const listTrashItems = () => request.get('/trash')

export const getTrashStats = () => request.get('/trash/stats')

export const clearTrash = (data) => request.post('/trash/clear', data)

export const restoreTrashItem = (id, conflictPolicy = 'rename') =>
  request.post(`/trash/${id}/restore`, null, { params: { conflict_policy: conflictPolicy } })

export const purgeTrashItem = (id) => request.delete(`/trash/${id}`)
