import request from '@/utils/request'

export const listTrashItems = () => request.get('/trash')

export const restoreTrashItem = (id, conflictPolicy = 'rename') =>
  request.post(`/trash/${id}/restore`, null, { params: { conflict_policy: conflictPolicy } })

export const purgeTrashItem = (id) => request.delete(`/trash/${id}`)
