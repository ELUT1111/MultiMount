/**
 * WebSocket 组合式函数 — 连接传输任务进度推送, 自动重连。
 */
import { ref, onUnmounted } from 'vue'

export function buildWebSocketUrl(path) {
  const apiOrigin = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') || window.location.origin
  const url = new URL(path, apiOrigin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}

export function useWebSocket(url, options = {}) {
  const { autoReconnect = true, reconnectInterval = 3000 } = options

  const data = ref(null)
  const connected = ref(false)
  let ws = null
  let reconnectTimer = null
  let heartbeatTimer = null
  let shouldReconnect = autoReconnect

  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function clearHeartbeatTimer() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function connect() {
    if (ws && [WebSocket.CONNECTING, WebSocket.OPEN].includes(ws.readyState)) return

    shouldReconnect = autoReconnect
    clearReconnectTimer()

    // 通过 Sec-WebSocket-Protocol 传递 token (避免 token 出现在 URL/日志中)
    const token = localStorage.getItem('access_token')
    ws = token
      ? new WebSocket(url, ['auth', token])
      : new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
      // 启动心跳 (每 30 秒)
      clearHeartbeatTimer()
      heartbeatTimer = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping')
      }, 30000)
    }

    ws.onmessage = (e) => {
      if (e.data === 'pong') return // 心跳响应忽略
      try {
        data.value = JSON.parse(e.data)
      } catch {
        data.value = e.data
      }
    }

    ws.onclose = () => {
      connected.value = false
      clearHeartbeatTimer()
      ws = null
      // 自动重连
      if (shouldReconnect) {
        reconnectTimer = setTimeout(connect, reconnectInterval)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }

  function disconnect() {
    shouldReconnect = false
    clearReconnectTimer()
    clearHeartbeatTimer()
    if (ws) {
      ws.close()
      ws = null
    }
    connected.value = false
  }

  // 组件卸载时自动断开
  onUnmounted(disconnect)

  return { data, connected, connect, disconnect }
}
