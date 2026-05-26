import request from '@/utils/request'

export const listTransfers = (params) => request.get('/transfers', { params })

export const getTransfer = (id) => request.get(`/transfers/${id}`)

export const createTransfer = (data) => request.post('/transfers', data)

export const pauseTransfer = (id) => request.post(`/transfers/${id}/pause`)

export const resumeTransfer = (id) => request.post(`/transfers/${id}/resume`)

export const cancelTransfer = (id) => request.delete(`/transfers/${id}`)

export const retryTransfer = (id) => request.post(`/transfers/${id}/retry`)
