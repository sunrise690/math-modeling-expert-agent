import 'dotenv/config'
import { resolve } from 'node:path'

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
  dataDir: process.env.DATA_DIR ? resolve(process.env.DATA_DIR) : resolve(process.cwd(), 'data'),
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
  openai: {
    apiKey: process.env.OPENAI_API_KEY || '',
    model: process.env.OPENAI_MODEL || 'gpt-5.6',
    codeInterpreter: process.env.OPENAI_CODE_INTERPRETER !== 'false',
    imageGeneration: process.env.OPENAI_IMAGE_GENERATION !== 'false',
    maxArtifacts: Math.max(1, Math.min(8, Number(process.env.OPENAI_MAX_ARTIFACTS || 4))),
    maxArtifactBytes: Math.max(256_000, Math.min(20_000_000, Number(process.env.OPENAI_MAX_ARTIFACT_BYTES || 8_000_000)))
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
