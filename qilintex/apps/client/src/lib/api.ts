import type { AgentResult, AuthPayload, AuthRealm, CompileResult, FriendsPayload, Project, User } from './types'

const ACTIVE_REALM_KEY = 'tonggao.authRealm'
const TOKEN_KEYS: Record<AuthRealm, string> = {
  team: 'tonggao.session.team',
  oauth: 'tonggao.session.oauth'
}
const DEVICE_KEY = 'tonggao.device'

export const apiUrl = __API_URL__
export const collabUrl = __COLLAB_URL__

export function getAuthRealm(): AuthRealm {
  return localStorage.getItem(ACTIVE_REALM_KEY) === 'oauth' ? 'oauth' : 'team'
}

export function setAuthRealm(realm: AuthRealm) {
  localStorage.setItem(ACTIVE_REALM_KEY, realm)
}

export function getToken(realm: AuthRealm = getAuthRealm()) {
  return localStorage.getItem(TOKEN_KEYS[realm]) || ''
}

export function setToken(token?: string, realm: AuthRealm = getAuthRealm()) {
  if (token) localStorage.setItem(TOKEN_KEYS[realm], token)
  else localStorage.removeItem(TOKEN_KEYS[realm])
}

export function getDeviceId() {
  const saved = localStorage.getItem(DEVICE_KEY)
  if (saved) return saved
  const id = typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : Array.from(crypto.getRandomValues(new Uint8Array(24)), (byte) => byte.toString(16).padStart(2, '0')).join('')
  localStorage.setItem(DEVICE_KEY, id)
  return id
}

async function request<T>(path: string, init: RequestInit = {}, realm: AuthRealm = getAuthRealm()): Promise<T> {
  const token = getToken(realm)
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  headers.set('X-Auth-Realm', realm)
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers,
    credentials: 'include'
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.error || `请求失败（${response.status}）`)
  return payload as T
}

export const api = {
  me: (realm: AuthRealm = getAuthRealm()) => request<AuthPayload>('/auth/me', {}, realm),
  teamLogin: (displayName: string, accessCode: string) => request<AuthPayload>('/auth/team', {
    method: 'POST', body: JSON.stringify({ displayName, accessCode, deviceId: getDeviceId() })
  }, 'team'),
  devLogin: (displayName: string) => request<AuthPayload>('/auth/dev', {
    method: 'POST', body: JSON.stringify({ displayName })
  }, 'team'),
  exchangeTicket: (ticket: string) => request<AuthPayload>('/auth/ticket', {
    method: 'POST', body: JSON.stringify({ ticket })
  }, 'oauth'),
  logout: (realm: AuthRealm = getAuthRealm()) => request<{ ok: true; realm: AuthRealm }>('/auth/logout', { method: 'POST' }, realm),
  authProviders: () => request<{
    team: { enabled: boolean; name: string; accessCodeRequired: boolean }
    qq: boolean
    wechat: boolean
    dev: boolean
  }>('/auth/providers'),
  projects: () => request<{ projects: Project[] }>('/api/projects'),
  createProject: (name: string) => request<{ project: Project }>('/api/projects', {
    method: 'POST', body: JSON.stringify({ name })
  }),
  createInvitation: (projectId: string) => request<{ token: string; url: string; expiresAt: string }>(`/api/projects/${projectId}/invitations`, { method: 'POST' }),
  acceptInvitation: (token: string) => request<{ project: Project }>(`/api/invitations/${encodeURIComponent(token)}/accept`, { method: 'POST' }),
  friends: () => request<FriendsPayload>('/api/friends'),
  searchUsers: (query: string) => request<{ users: User[] }>(`/api/users/search?q=${encodeURIComponent(query)}`),
  requestFriend: (userId: string) => request<{ ok: true }>('/api/friends/requests', {
    method: 'POST', body: JSON.stringify({ userId })
  }),
  acceptFriend: (requestId: string) => request<{ ok: true }>(`/api/friends/requests/${requestId}/accept`, { method: 'POST' }),
  compile: (projectId: string, source: string) => request<CompileResult>(`/api/projects/${projectId}/compile`, {
    method: 'POST', body: JSON.stringify({ source })
  }),
  askAgent: (projectId: string, source: string, message: string) => request<AgentResult>(`/api/projects/${projectId}/agent`, {
    method: 'POST', body: JSON.stringify({ source, message })
  })
}
