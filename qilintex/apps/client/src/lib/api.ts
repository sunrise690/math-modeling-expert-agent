import type { AgentMode, AuthPayload, AuthRealm, CompileResult, DirectMessage, FriendsPayload, Project, ProjectFileEntry, User } from './types'
import { localAgent } from './local-agent'

const ACTIVE_REALM_KEY = 'tonggao.authRealm'
const TOKEN_KEYS: Record<AuthRealm, string> = {
  team: 'tonggao.session.team',
  oauth: 'tonggao.session.oauth'
}
type BrowserLocation = Pick<Location, 'protocol' | 'host'>

function trimTrailingSlashes(value: string) {
  return value.trim().replace(/\/+$/, '')
}

export function resolveServiceUrls(
  configuredApiUrl: string,
  configuredCollabUrl: string,
  currentLocation: BrowserLocation | undefined = typeof location === 'undefined' ? undefined : location
) {
  const explicitApiUrl = trimTrailingSlashes(configuredApiUrl)
  const explicitCollabUrl = trimTrailingSlashes(configuredCollabUrl)
  const isFileApp = currentLocation?.protocol === 'file:'

  return {
    apiUrl: explicitApiUrl || (isFileApp ? 'http://127.0.0.1:4318' : ''),
    collabUrl: explicitCollabUrl || (isFileApp || !currentLocation
      ? 'ws://127.0.0.1:4319'
      : `${currentLocation.protocol === 'https:' ? 'wss:' : 'ws:'}//${currentLocation.host}/collab`)
  }
}

const serviceUrls = resolveServiceUrls(__API_URL__, __COLLAB_URL__)
export const apiUrl = serviceUrls.apiUrl
export const collabUrl = serviceUrls.collabUrl

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
  teamLogin: (accountId: string, accessCode: string, email = '') => request<AuthPayload>('/auth/team', {
    method: 'POST', body: JSON.stringify({ accountId, accessCode, email })
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
  profile: () => request<{ user: User }>('/api/profile'),
  updateProfile: (payload: { displayName: string; email: string; avatarUrl: string }) => request<{ user: User }>('/api/profile', {
    method: 'PATCH', body: JSON.stringify(payload)
  }),
  createProject: (name: string) => request<{ project: Project }>('/api/projects', {
    method: 'POST', body: JSON.stringify({ name })
  }),
  localAgentHealth: () => localAgent.health(),
  agentConfig: () => localAgent.config(),
  testAgentConfig: (payload: Record<string, unknown>) => localAgent.testConfig(payload),
  saveAgentConfig: (payload: Record<string, unknown>) => localAgent.saveConfig(payload),
  startCodexLogin: () => localAgent.startCodexLogin(),
  codexLoginStatus: (sessionId: string) => localAgent.codexLoginStatus(sessionId),
  cancelCodexLogin: (sessionId: string) => localAgent.cancelCodexLogin(sessionId),
  projectFiles: (projectId: string) => request<{ files: ProjectFileEntry[] }>(`/api/projects/${projectId}/files`),
  createProjectFolder: (projectId: string, path: string) => request<{ path: string }>(`/api/projects/${projectId}/folders`, {
    method: 'POST', body: JSON.stringify({ path })
  }),
  uploadProjectFile: (projectId: string, path: string, content: Blob) => request<{ file: ProjectFileEntry }>(
    `/api/projects/${projectId}/files?path=${encodeURIComponent(path)}`,
    { method: 'PUT', headers: { 'Content-Type': 'application/octet-stream' }, body: content }
  ),
  uploadAgentFile: (_projectId: string, file: File) => localAgent.upload(file),
  deleteAgentFile: (_projectId: string, uploadId: string) => localAgent.deleteUpload(uploadId),
  createInvitation: (projectId: string) => request<{ token: string; url: string; expiresAt: string }>(`/api/projects/${projectId}/invitations`, { method: 'POST' }),
  acceptInvitation: (token: string) => request<{ project: Project }>(`/api/invitations/${encodeURIComponent(token)}/accept`, { method: 'POST' }),
  friends: () => request<FriendsPayload>('/api/friends'),
  searchUsers: (query: string) => request<{ users: User[] }>(`/api/users/search?q=${encodeURIComponent(query)}`),
  requestFriend: (userId: string) => request<{ ok: true }>('/api/friends/requests', {
    method: 'POST', body: JSON.stringify({ userId })
  }),
  acceptFriend: (requestId: string) => request<{ ok: true }>(`/api/friends/requests/${requestId}/accept`, { method: 'POST' }),
  directMessages: (friendId: string) => request<{ messages: DirectMessage[] }>(`/api/friends/${encodeURIComponent(friendId)}/messages`),
  sendDirectMessage: (friendId: string, body: string) => request<{ message: DirectMessage }>(`/api/friends/${encodeURIComponent(friendId)}/messages`, {
    method: 'POST', body: JSON.stringify({ body })
  }),
  compile: (projectId: string, source: string) => request<CompileResult>(`/api/projects/${projectId}/compile`, {
    method: 'POST', body: JSON.stringify({ source })
  }),
  askAgent: (_projectId: string, source: string, message: string, mode: AgentMode = 'auto', uploads: string[] = []) => localAgent.ask(source, message, mode, uploads)
}
