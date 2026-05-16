import request from '@/utils/request'

export const getMountPermissions = (mountId) => request.get(`/mounts/${mountId}/permissions`)

export const grantPermission = (mountId, data) => request.post(`/mounts/${mountId}/permissions`, data)

export const revokePermission = (mountId, userId) => request.delete(`/mounts/${mountId}/permissions/${userId}`)

export const requestAccess = (mountId, data) => request.post(`/mounts/${mountId}/request-access`, data)
