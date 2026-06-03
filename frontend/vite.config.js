import fs from 'fs'
import nodeHttp from 'http'
import nodeHttps from 'https'
import path from 'path'
import { fileURLToPath } from 'url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

function resolveConfigPath(value) {
  return path.isAbsolute(value) ? value : path.resolve(__dirname, value)
}

function httpsConfig(env) {
  if (env.VITE_DEV_HTTPS !== 'true') return false
  const certPath = resolveConfigPath(env.VITE_HTTPS_CERT || '../backend/certs/localhost+3.pem')
  const keyPath = resolveConfigPath(env.VITE_HTTPS_KEY || '../backend/certs/localhost+3-key.pem')
  return {
    cert: fs.readFileSync(certPath),
    key: fs.readFileSync(keyPath),
  }
}

function fetchRedirectPolicy(proxyTarget) {
  return new Promise((resolve) => {
    const target = new URL('/api/v1/system/https/redirect-policy', proxyTarget)
    const client = target.protocol === 'https:' ? nodeHttps : nodeHttp
    const options = {
      hostname: target.hostname,
      port: target.port || (target.protocol === 'https:' ? 443 : 80),
      path: `${target.pathname}${target.search}`,
      method: 'GET',
      rejectUnauthorized: false,
    }

    const req = client.request(options, (res) => {
      let body = ''
      res.setEncoding('utf8')
      res.on('data', (chunk) => { body += chunk })
      res.on('end', () => {
        try {
          resolve(JSON.parse(body))
        } catch {
          resolve(null)
        }
      })
    })
    req.on('error', () => resolve(null))
    req.setTimeout(3000, () => {
      req.destroy()
      resolve(null)
    })
    req.end()
  })
}

function httpRedirectPlugin(env, proxyTarget) {
  if (env.VITE_DEV_HTTPS !== 'true') return null

  const redirectPort = Number(env.VITE_HTTP_REDIRECT_PORT || 5174)
  if (!redirectPort) return null

  let redirectServer
  return {
    name: 'mounthub-http-to-https-redirect',
    configureServer(viteServer) {
      redirectServer = nodeHttp.createServer(async (req, res) => {
        const policy = await fetchRedirectPolicy(proxyTarget)
        if (!policy?.redirect_enabled) {
          res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
          res.end('MountHub HTTPS redirect is disabled.')
          return
        }

        const host = req.headers.host || `localhost:${redirectPort}`
        const hostname = host.replace(/:\d+$/, '')
        const httpsPort = viteServer.config.server.port || 5173
        const location = `https://${hostname}:${httpsPort}${req.url || '/'}`
        res.writeHead(302, { Location: location })
        res.end()
      })

      redirectServer.listen(redirectPort, '0.0.0.0', () => {
        viteServer.config.logger.info(`  ➜  HTTP redirect: http://localhost:${redirectPort}/`)
      })
      viteServer.httpServer?.once('close', () => {
        redirectServer?.close()
      })
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_PROXY_TARGET || 'http://127.0.0.1:8014'
  const plugins = [vue()]
  const redirectPlugin = httpRedirectPlugin(env, proxyTarget)
  if (redirectPlugin) plugins.push(redirectPlugin)

  return {
    plugins,
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined
            if (id.includes('@element-plus/icons-vue')) return 'vendor-icons'
            if (id.includes('element-plus')) return 'vendor-element-plus'
            if (id.includes('echarts')) return 'vendor-echarts'
            if (id.includes('vue') || id.includes('pinia') || id.includes('vue-router')) return 'vendor-vue'
            return 'vendor'
          },
        },
      },
    },
    server: {
      https: httpsConfig(env),
      port: 5173,
      allowedHosts: true,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
        },
      },
    },
    resolve: {
      alias: {
        '@': '/src',
      },
    },
  }
})
