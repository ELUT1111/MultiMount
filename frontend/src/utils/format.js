/**
 * 字节数格式化为人类可读大小
 */
export function formatSize(bytes) {
  if (bytes == null || bytes < 0) return '未知'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return i === 0 ? `${bytes} B` : `${bytes.toFixed(1)} ${units[i]}`
}

/**
 * 日期时间格式化
 */
export function formatTime(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * 传输速度格式化
 */
export function formatSpeed(bytesPerSec) {
  if (!bytesPerSec) return '-'
  return formatSize(bytesPerSec) + '/s'
}
