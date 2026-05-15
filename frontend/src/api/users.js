import request from '@/utils/request'

export const listUsers = (params) => request.get('/users', { params })

export const getMe = () => request.get('/users/me')

export const createUser = (data) => request.post('/users', data)

export const updateUser = (id, data) => request.put(`/users/${id}`, data)

export const deleteUser = (id) => request.delete(`/users/${id}`)

export const listRoles = () => request.get('/users/roles')

export const createRole = (data) => request.post('/users/roles', data)

export const updateRole = (id, data) => request.put(`/users/roles/${id}`, data)

export const deleteRole = (id) => request.delete(`/users/roles/${id}`)
