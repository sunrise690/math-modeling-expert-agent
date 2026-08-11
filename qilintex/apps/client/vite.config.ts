import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '../../', '')
  const developmentApiUrl = process.env.PUBLIC_API_URL || env.PUBLIC_API_URL || 'http://localhost:4318'
  const developmentCollabUrl = process.env.PUBLIC_COLLAB_URL || env.PUBLIC_COLLAB_URL || 'ws://localhost:4319'
  const clientApiUrl = process.env.QILINTEX_CLIENT_API_URL || env.QILINTEX_CLIENT_API_URL || ''
  const clientCollabUrl = process.env.QILINTEX_CLIENT_COLLAB_URL || env.QILINTEX_CLIENT_COLLAB_URL || ''
  return {
    base: './',
    plugins: [
      react(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['logo.svg', 'app-icon.jpg'],
        manifest: {
          name: '数模工作台 · Agent 与 QilinTeX',
          short_name: '数模工作台',
          description: '数学建模 Agent 与 QilinTeX 协作论文一体化工作台',
          theme_color: '#181818',
          background_color: '#181818',
          display: 'standalone',
          icons: [
            { src: 'app-icon.jpg', sizes: '1080x1080', type: 'image/jpeg', purpose: 'any' },
            { src: 'pwa-192.svg', sizes: '192x192', type: 'image/svg+xml' },
            { src: 'pwa-512.svg', sizes: '512x512', type: 'image/svg+xml' }
          ]
        }
      })
    ],
    define: {
      __API_URL__: JSON.stringify(clientApiUrl || (mode === 'development' ? developmentApiUrl : '')),
      __COLLAB_URL__: JSON.stringify(clientCollabUrl || (mode === 'development' ? developmentCollabUrl : ''))
    },
    server: { port: 5173, strictPort: true }
  }
})
