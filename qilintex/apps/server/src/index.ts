import express, { type ErrorRequestHandler } from 'express'
import cors from 'cors'
import cookieParser from 'cookie-parser'
import { authMiddleware, authRouter } from './auth.js'
import { startCollaboration } from './collaboration.js'
import { config } from './config.js'
import { apiRouter } from './routes.js'
import { Store } from './store.js'

async function main() {
  const store = new Store()
  await store.init()

  const app = express()
  app.disable('x-powered-by')
  if (process.env.NODE_ENV === 'production') app.set('trust proxy', 1)
  app.use(cors({
    origin: (origin, callback) => {
      const loopbackDevelopment = process.env.NODE_ENV !== 'production' && Boolean(origin && /^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(origin))
      callback(null, !origin || config.clientUrls.includes(origin.replace(/\/$/, '')) || loopbackDevelopment)
    },
    credentials: true
  }))
  app.use(express.json({ limit: '1mb' }))
  app.use(cookieParser())
  app.use(authMiddleware(store))

  app.get('/health', (_request, response) => response.json({ ok: true, collaborationPort: config.collaborationPort }))
  app.get('/updates/latest', (request, response) => {
    const platform = request.query.platform === 'ios' ? 'ios' : 'android'
    response.json({
      version: config.updates.version,
      releaseNotes: config.updates.releaseNotes,
      storeUrl: platform === 'ios' ? config.updates.iosStoreUrl : config.updates.androidStoreUrl
    })
  })
  app.use('/auth', authRouter(store))
  app.use('/api', apiRouter(store))

  const errorHandler: ErrorRequestHandler = (error, _request, response, _next) => {
    console.error(error)
    response.status(500).json({ error: error instanceof Error ? error.message : '服务端内部错误。' })
  }
  app.use(errorHandler)

  app.listen(config.port, config.host, () => console.log(`REST API: http://${config.host}:${config.port}`))
  await startCollaboration(store)
  console.log(`Collaboration: ws://localhost:${config.collaborationPort}`)
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
