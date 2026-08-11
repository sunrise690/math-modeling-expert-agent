import { createHash, randomBytes, timingSafeEqual } from 'node:crypto'
import { Router, type NextFunction, type Request, type Response } from 'express'
import { jwtVerify, SignJWT } from 'jose'
import { config } from './config.js'
import { Store, toPublicUser, type Provider, type StoredUser } from './store.js'

export type AuthRealm = 'team' | 'oauth'

const SESSION_COOKIES: Record<AuthRealm, string> = {
  team: 'tg_team_session',
  oauth: 'tg_oauth_session'
}

declare global {
  namespace Express {
    interface Request {
      user?: StoredUser
      authRealm?: AuthRealm
    }
  }
}

const secret = new TextEncoder().encode(config.sessionSecret)
const states = new Map<string, { provider: 'qq' | 'wechat'; platform: 'web' | 'desktop'; expires: number }>()
const tickets = new Map<string, { userId: string; realm: AuthRealm; expires: number }>()
const teamFailures = new Map<string, { count: number; resetAt: number }>()

const TEAM_ATTEMPT_LIMIT = 5
const TEAM_ATTEMPT_WINDOW = 10 * 60_000

export function normalizeTeamAccountId(value: string) {
  const accountId = String(value || '').normalize('NFKC').trim().toLocaleLowerCase()
  if (!/^[a-z0-9][a-z0-9_-]{2,23}$/.test(accountId)) {
    throw new Error('账号 ID 需为 3–24 位小写字母、数字、下划线或连字符，并以字母或数字开头。')
  }
  return accountId
}

export function normalizeOptionalEmail(value: string) {
  const email = String(value || '').normalize('NFKC').trim().toLocaleLowerCase()
  if (!email) return undefined
  if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error('邮箱格式无效。')
  return email
}

export function matchesAccessCode(input: string, expected: string) {
  if (!expected) return true
  const inputHash = createHash('sha256').update(input).digest()
  const expectedHash = createHash('sha256').update(expected).digest()
  return timingSafeEqual(inputHash, expectedHash)
}

export function authRealmForProvider(provider: Provider): AuthRealm {
  return provider === 'team' || provider === 'dev' ? 'team' : 'oauth'
}

function teamAttemptKey(request: Request) {
  return request.ip || request.socket.remoteAddress || 'unknown'
}

function teamAttemptBlocked(key: string) {
  const attempt = teamFailures.get(key)
  if (!attempt) return false
  if (attempt.resetAt <= Date.now()) {
    teamFailures.delete(key)
    return false
  }
  return attempt.count >= TEAM_ATTEMPT_LIMIT
}

function recordTeamFailure(key: string) {
  const current = teamFailures.get(key)
  if (!current || current.resetAt <= Date.now()) {
    teamFailures.set(key, { count: 1, resetAt: Date.now() + TEAM_ATTEMPT_WINDOW })
    return
  }
  current.count += 1
}

export async function signSession(user: StoredUser) {
  return new SignJWT({ provider: user.provider, realm: authRealmForProvider(user.provider) })
    .setProtectedHeader({ alg: 'HS256' })
    .setSubject(user.id)
    .setIssuedAt()
    .setExpirationTime('30d')
    .sign(secret)
}

export async function verifySessionDetails(token: string, expectedRealm?: AuthRealm) {
  const { payload } = await jwtVerify(token, secret)
  if (!payload.sub) throw new Error('登录凭据无效。')
  const provider = payload.provider
  if (provider !== 'team' && provider !== 'dev' && provider !== 'qq' && provider !== 'wechat') throw new Error('登录来源无效。')
  const inferredRealm = authRealmForProvider(provider)
  const realm = payload.realm === 'team' || payload.realm === 'oauth' ? payload.realm : inferredRealm
  if (realm !== inferredRealm || (expectedRealm && realm !== expectedRealm)) throw new Error('登录方式不匹配。')
  return { userId: payload.sub, provider, realm }
}

export async function verifySession(token: string, expectedRealm?: AuthRealm) {
  return (await verifySessionDetails(token, expectedRealm)).userId
}

function requestedRealm(request: Request): AuthRealm | undefined {
  const value = request.get('x-auth-realm') || request.query.realm
  return value === 'team' || value === 'oauth' ? value : undefined
}

function bearerToken(request: Request) {
  const authorization = request.headers.authorization
  return authorization?.startsWith('Bearer ') ? authorization.slice(7) : ''
}

export function authMiddleware(store: Store) {
  return async (request: Request, _response: Response, next: NextFunction) => {
    const requested = requestedRealm(request)
    const bearer = bearerToken(request)
    const cookieRealm = requested || 'team'
    const token = bearer || request.cookies?.[SESSION_COOKIES[cookieRealm]] || ''
    if (token) {
      try {
        const session = await verifySessionDetails(token, bearer ? requested : cookieRealm)
        const user = store.userById(session.userId)
        if (!user || user.provider !== session.provider || authRealmForProvider(user.provider) !== session.realm) throw new Error('登录用户不匹配。')
        request.user = user
        request.authRealm = session.realm
      } catch {
        request.user = undefined
        request.authRealm = requested || cookieRealm
      }
    } else {
      request.authRealm = requested || cookieRealm
    }
    next()
  }
}

export function requireUser(request: Request, response: Response, next: NextFunction) {
  if (!request.user) return response.status(401).json({ error: '请先登录。' })
  next()
}

function setSessionCookie(response: Response, realm: AuthRealm, token: string) {
  response.cookie(SESSION_COOKIES[realm], token, { httpOnly: true, sameSite: 'lax', secure: process.env.NODE_ENV === 'production', maxAge: 30 * 86400_000, path: '/' })
}

function makeState(provider: 'qq' | 'wechat', platform: 'web' | 'desktop') {
  const state = randomBytes(24).toString('base64url')
  states.set(state, { provider, platform, expires: Date.now() + 10 * 60_000 })
  return state
}

function consumeState(state: string, provider: 'qq' | 'wechat') {
  const entry = states.get(state)
  states.delete(state)
  if (!entry || entry.provider !== provider || entry.expires < Date.now()) throw new Error('登录状态无效或已过期。')
  return entry
}

async function completeLogin(response: Response, store: Store, user: StoredUser, platform: 'web' | 'desktop') {
  const realm = authRealmForProvider(user.provider)
  const token = await signSession(user)
  if (platform === 'desktop') {
    const ticket = randomBytes(24).toString('base64url')
    tickets.set(ticket, { userId: user.id, realm, expires: Date.now() + 2 * 60_000 })
    return response.redirect(`tonggaotex://auth?ticket=${encodeURIComponent(ticket)}`)
  }
  setSessionCookie(response, realm, token)
  response.redirect(`${config.clientUrl}/#session=${encodeURIComponent(token)}&realm=${realm}`)
}

async function getJson(url: URL) {
  const response = await fetch(url, { headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(15_000) })
  if (!response.ok) throw new Error(`开放平台请求失败（${response.status}）`)
  return response.json() as Promise<Record<string, unknown>>
}

export function authRouter(store: Store) {
  const router = Router()

  router.get('/providers', (_request, response) => response.json({
    team: {
      enabled: config.team.enabled,
      name: config.team.name,
      accessCodeRequired: Boolean(config.team.accessCode)
    },
    qq: Boolean(config.qq.appId && config.qq.appSecret),
    wechat: Boolean(config.wechat.appId && config.wechat.appSecret),
    dev: config.allowDevLogin
  }))

  router.get('/me', (request, response) => {
    if (!request.user) return response.status(401).json({ error: '未登录。' })
    response.json({ user: toPublicUser(request.user, true), realm: request.authRealm || authRealmForProvider(request.user.provider) })
  })

  router.post('/team', async (request, response) => {
    if (!config.team.enabled) return response.status(503).json({ error: '团队登录尚未配置。' })

    const attemptKey = teamAttemptKey(request)
    if (teamAttemptBlocked(attemptKey)) {
      return response.status(429).json({ error: '尝试次数过多，请 10 分钟后再试。' })
    }

    let accountId = ''
    let email: string | undefined
    try { accountId = normalizeTeamAccountId(request.body?.accountId) }
    catch (error) { return response.status(400).json({ error: error instanceof Error ? error.message : '账号 ID 无效。' }) }
    try { email = normalizeOptionalEmail(request.body?.email) }
    catch (error) { return response.status(400).json({ error: error instanceof Error ? error.message : '邮箱格式无效。' }) }
    const accessCode = String(request.body?.accessCode || '').slice(0, 128)
    if (!matchesAccessCode(accessCode, config.team.accessCode)) {
      recordTeamFailure(attemptKey)
      return response.status(401).json({ error: '团队口令不正确。' })
    }

    teamFailures.delete(attemptKey)
    let user: StoredUser
    try { user = await store.loginTeamUser(accountId, email) }
    catch (error) { return response.status(409).json({ error: error instanceof Error ? error.message : '账号登录失败。' }) }
    const token = await signSession(user)
    setSessionCookie(response, 'team', token)
    response.json({ user: toPublicUser(user, true), token, realm: 'team' })
  })

  router.post('/dev', async (request, response) => {
    if (!config.allowDevLogin) return response.status(404).json({ error: '开发登录未启用。' })
    const displayName = String(request.body?.displayName || '').trim().slice(0, 24)
    if (!displayName) return response.status(400).json({ error: '请输入显示名称。' })
    const providerId = createHash('sha256').update(displayName.toLocaleLowerCase()).digest('hex')
    const user = await store.upsertUser({ provider: 'dev', providerId, displayName })
    const token = await signSession(user)
    setSessionCookie(response, 'team', token)
    response.json({ user: toPublicUser(user), token, realm: 'team' })
  })

  router.post('/ticket', async (request, response) => {
    const ticket = String(request.body?.ticket || '')
    const entry = tickets.get(ticket)
    tickets.delete(ticket)
    if (!entry || entry.expires < Date.now()) return response.status(400).json({ error: '桌面登录凭据无效或已过期。' })
    const user = store.userById(entry.userId)
    if (!user) return response.status(400).json({ error: '用户不存在。' })
    if (authRealmForProvider(user.provider) !== entry.realm) return response.status(400).json({ error: '登录方式不匹配。' })
    const token = await signSession(user)
    response.json({ user: toPublicUser(user), token, realm: entry.realm })
  })

  router.post('/logout', (request, response) => {
    const realm = requestedRealm(request) || request.authRealm || 'team'
    response.clearCookie(SESSION_COOKIES[realm], { path: '/' })
    response.json({ ok: true, realm })
  })

  router.get('/qq/start', (request, response) => {
    if (!config.qq.appId || !config.qq.appSecret) return response.status(503).json({ error: 'QQ 登录尚未配置。' })
    const platform = request.query.platform === 'desktop' ? 'desktop' : 'web'
    const url = new URL('https://graph.qq.com/oauth2.0/authorize')
    url.search = new URLSearchParams({ response_type: 'code', client_id: config.qq.appId, redirect_uri: config.qq.redirectUri, state: makeState('qq', platform), scope: 'get_user_info' }).toString()
    response.redirect(url.toString())
  })

  router.get('/qq/callback', async (request, response, next) => {
    try {
      const code = String(request.query.code || '')
      const state = consumeState(String(request.query.state || ''), 'qq')
      if (!code) throw new Error('QQ 未返回授权码。')

      const tokenUrl = new URL('https://graph.qq.com/oauth2.0/token')
      tokenUrl.search = new URLSearchParams({ grant_type: 'authorization_code', client_id: config.qq.appId, client_secret: config.qq.appSecret, code, redirect_uri: config.qq.redirectUri, fmt: 'json' }).toString()
      const tokenData = await getJson(tokenUrl)
      const accessToken = String(tokenData.access_token || '')
      if (!accessToken) throw new Error('QQ 未返回 access_token。')

      const identityUrl = new URL('https://graph.qq.com/oauth2.0/me')
      identityUrl.search = new URLSearchParams({ access_token: accessToken, fmt: 'json' }).toString()
      const identity = await getJson(identityUrl)
      const openid = String(identity.openid || '')
      if (!openid) throw new Error('QQ 未返回 openid。')

      const profileUrl = new URL('https://graph.qq.com/user/get_user_info')
      profileUrl.search = new URLSearchParams({ access_token: accessToken, oauth_consumer_key: config.qq.appId, openid, fmt: 'json' }).toString()
      const profile = await getJson(profileUrl)
      const user = await store.upsertUser({ provider: 'qq', providerId: openid, displayName: String(profile.nickname || 'QQ 用户'), avatarUrl: String(profile.figureurl_qq_2 || profile.figureurl_qq_1 || '') || undefined })
      await completeLogin(response, store, user, state.platform)
    } catch (error) { next(error) }
  })

  router.get('/wechat/start', (request, response) => {
    if (!config.wechat.appId || !config.wechat.appSecret) return response.status(503).json({ error: '微信登录尚未配置。' })
    const platform = request.query.platform === 'desktop' ? 'desktop' : 'web'
    const url = new URL('https://open.weixin.qq.com/connect/qrconnect')
    url.search = new URLSearchParams({ appid: config.wechat.appId, redirect_uri: config.wechat.redirectUri, response_type: 'code', scope: 'snsapi_login', state: makeState('wechat', platform) }).toString()
    response.redirect(`${url.toString()}#wechat_redirect`)
  })

  router.get('/wechat/callback', async (request, response, next) => {
    try {
      const code = String(request.query.code || '')
      const state = consumeState(String(request.query.state || ''), 'wechat')
      if (!code) throw new Error('微信未返回授权码。')

      const tokenUrl = new URL('https://api.weixin.qq.com/sns/oauth2/access_token')
      tokenUrl.search = new URLSearchParams({ appid: config.wechat.appId, secret: config.wechat.appSecret, code, grant_type: 'authorization_code' }).toString()
      const tokenData = await getJson(tokenUrl)
      const accessToken = String(tokenData.access_token || '')
      const openid = String(tokenData.openid || '')
      if (!accessToken || !openid) throw new Error(String(tokenData.errmsg || '微信未返回登录凭据。'))

      const profileUrl = new URL('https://api.weixin.qq.com/sns/userinfo')
      profileUrl.search = new URLSearchParams({ access_token: accessToken, openid, lang: 'zh_CN' }).toString()
      const profile = await getJson(profileUrl)
      const providerId = String(profile.unionid || openid)
      const user = await store.upsertUser({ provider: 'wechat', providerId, displayName: String(profile.nickname || '微信用户'), avatarUrl: String(profile.headimgurl || '') || undefined })
      await completeLogin(response, store, user, state.platform)
    } catch (error) { next(error) }
  })

  return router
}
