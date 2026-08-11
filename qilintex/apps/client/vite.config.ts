import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '../../', '')
  return {
    base: './',
    plugins: [
      react(),
      VitePWA({
        registerType: 'prompt',
        includeAssets: ['logo.svg'],
        manifest: {
          name: 'Qilintex',
          short_name: 'Qilintex',
          description: '多人实时协作 LaTeX 与 AI 写作工作台',
          theme_color: '#0F0F0F',
          background_color: '#0F0F0F',
          display: 'standalone',
          icons: [
            { src: 'pwa-192.svg', sizes: '192x192', type: 'image/svg+xml' },
            { src: 'pwa-512.svg', sizes: '512x512', type: 'image/svg+xml' }
          ]
        }
      })
    ],
    define: {
      __API_URL__: JSON.stringify(process.env.PUBLIC_API_URL || env.PUBLIC_API_URL || 'http://localhost:4318'),
      __COLLAB_URL__: JSON.stringify(process.env.PUBLIC_COLLAB_URL || env.PUBLIC_COLLAB_URL || 'ws://localhost:4319')
    },
    server: { port: 5173, strictPort: true }
  }
})
