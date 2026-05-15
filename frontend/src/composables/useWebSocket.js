/**
 * WebSocket 组合式函数 — 连接传输任务进度推送, 自动重连。
 */
import { ref, onUnmounted } from 'vue'

export function useWebSocket(url, options = {}) {
  const { autoReconnect = true, reconnectInterval = 3000 } = options

  const data = ref(null)
  const connected = ref(false)
  let ws = null
  let reconnectTimer = null

  function connect() {
    // 从 localStorage 获取 token 附加到 URL
    const token = localStorage.getItem('access_token')
    const wsUrl = token ? `${url}?token=${encodeURIComponent(token)}` : url

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      connected.value = true
      // 启动心跳 (每 30 秒)
      if (ws._heartbeat) clearInterval(ws._heartbeat)
      ws._heartbeat = setInterval(() => {
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
      if (ws._heartbeat) clearInterval(ws._heartbeat)
      // 自动重连
      if (autoReconnect) {
        reconnectTimer = setTimeout(connect, reconnectInterval)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (ws) {
      ws.close()
      ws = null
    }
  }

  // 组件卸载时自动断开
  onUnmounted(disconnect)

  return { data, connected, connect, disconnect }
}
