import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { config as loadEnv } from 'dotenv'

function findServerDirectory() {
  const starts = [process.argv[1] ? dirname(resolve(process.argv[1])) : '', process.cwd()].filter(Boolean)
  for (const start of starts) {
    let candidate = start
    for (let depth = 0; depth < 6; depth += 1) {
      if (existsSync(join(candidate, 'package.json')) && existsSync(join(candidate, 'src'))) return candidate
      const parent = dirname(candidate)
      if (parent === candidate) break
      candidate = parent
    }
  }
  return resolve(process.cwd())
}

const serverDirectory = findServerDirectory()

function findWorkspaceDirectory() {
  let candidate = serverDirectory
  for (let depth = 0; depth < 6; depth += 1) {
    if (existsSync(join(candidate, 'pnpm-workspace.yaml'))) return candidate
    const parent = dirname(candidate)
    if (parent === candidate) break
    candidate = parent
  }
  return resolve(serverDirectory, '..', '..')
}

const workspaceDirectory = findWorkspaceDirectory()
loadEnv({ path: resolve(workspaceDirectory, '..', '.env') })
loadEnv({ path: resolve(workspaceDirectory, '.env'), override: true })

const parsedClientUrls = (process.env.CLIENT_URLS || process.env.CLIENT_URL || 'http://localhost:5173')
  .split(',')
  .map((url) => url.trim().replace(/\/$/, ''))
  .filter(Boolean)
const configuredClientUrls = parsedClientUrls.length ? parsedClientUrls : ['http://localhost:5173']
export const config = {
  host: process.env.HOST || '0.0.0.0',
  port: Number(process.env.PORT || 4318),
  collaborationPort: Number(process.env.COLLAB_PORT || 4319),
  clientUrl: configuredClientUrls[0],
  clientUrls: configuredClientUrls,
  sessionSecret: process.env.SESSION_SECRET || 'development-only-change-this-secret-before-release',
  allowDevLogin: process.env.ALLOW_DEV_LOGIN === 'true' || process.env.NODE_ENV !== 'production',
  team: {
    name: process.env.TEAM_NAME?.trim() || '内部团队',
    accessCode: process.env.TEAM_ACCESS_CODE || '',
    enabled: Boolean(process.env.TEAM_ACCESS_CODE) || process.env.NODE_ENV !== 'production'
  },
  dataDir: process.env.DATA_DIR ? resolve(serverDirectory, process.env.DATA_DIR) : resolve(serverDirectory, 'data'),
  qq: {
    appId: process.env.QQ_APP_ID || '',
    appSecret: process.env.QQ_APP_SECRET || '',
    redirectUri: process.env.QQ_REDIRECT_URI || `http://localhost:${process.env.PORT || 4318}/auth/qq/callback`
  },
  wechat: {
    appId: process.env.WECHAT_APP_ID || '',
    appSecret: process.env.WECHAT_APP_SECRET || '',
    redirectUri: process.env.WECHAT_REDIRECT_URI || `http://localhost:${process.env.PORT || 4318}/auth/wechat/callback`
  },
  tex: {
    engine: process.env.TEX_ENGINE || 'tectonic',
    path: process.env.TEX_ENGINE_PATH || '',
    latexmkEngine: process.env.TEX_LATEXMK_ENGINE === 'xelatex' ? 'xelatex' : 'pdf'
  },
  updates: {
    version: process.env.APP_LATEST_VERSION || '0.1.0',
    releaseNotes: process.env.APP_RELEASE_NOTES || '',
    androidStoreUrl: process.env.ANDROID_STORE_URL || '',
    iosStoreUrl: process.env.IOS_STORE_URL || ''
  }
}
