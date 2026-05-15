import request from '@/utils/request'

export const listMounts = () => request.get('/mounts')

export const getMount = (id) => request.get(`/mounts/${id}`)

export const createMount = (data) => request.post('/mounts', data)

export const updateMount = (id, data) => request.put(`/mounts/${id}`, data)

export const deleteMount = (id) => request.delete(`/mounts/${id}`)

export const testConnection = (id) => request.post(`/mounts/${id}/test`)
