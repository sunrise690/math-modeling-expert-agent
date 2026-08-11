export type AuthRealm = 'team' | 'oauth'

export interface User {
  id: string
  handle: string
  displayName: string
  email?: string
  avatarUrl?: string
  provider: 'team' | 'qq' | 'wechat' | 'dev'
}

export interface Project {
  id: string
  name: string
  ownerId: string
  role: 'owner' | 'editor' | 'viewer'
  updatedAt: string
}

export interface ProjectFileEntry {
  path: string
  kind: 'file' | 'folder'
  size: number
  editable: boolean
}

export interface FriendRequest {
  id: string
  direction: 'incoming' | 'outgoing'
  status: 'pending'
  user: User
  createdAt: string
}

export interface FriendsPayload {
  friends: User[]
  requests: FriendRequest[]
}

export interface DirectMessage {
  id: string
  fromId: string
  toId: string
  body: string
  createdAt: string
}

export interface AgentProviderProfile {
  model: string
  baseUrl: string
  apiKeyConfigured?: boolean
  reasoningEffort?: string
  models?: Array<{ id: string; displayName?: string; isDefault?: boolean }>
}

export interface AgentProviderOption {
  id: string
  label: string
  description: string
  requiresApiKey: boolean
  defaultModel?: string
  defaultBaseUrl?: string
  profile: AgentProviderProfile
}

export interface AgentConfig {
  activeProvider: string
  configLocked: boolean
  providerCatalog: AgentProviderOption[]
  codexStatus?: { available?: boolean; authenticated?: boolean; reason?: string }
}

export interface CodexLoginSession {
  id: string
  mode: 'device-code' | 'browser-callback'
  status: 'pending' | 'completed' | 'failed' | 'cancelled' | 'expired'
  authUrl: string
  verificationUrl: string
  userCode: string
  message: string
  expiresAt: string
}

export interface AgentUpload {
  id: string
  name: string
  size: number
  mimeType: string
  inspection?: Record<string, unknown>
}

export interface AuthPayload {
  user: User
  token?: string
  realm: AuthRealm
}

export interface CompileResult {
  ok: boolean
  pdfBase64?: string
  log: string
  engine?: string
}

export type AgentMode = 'auto' | 'solver' | 'cumcm' | 'paper' | 'reviewer'

export interface AgentArtifact {
  id: string
  name: string
  mimeType: string
  base64: string
  kind: 'data_figure' | 'generated_image' | 'modeling_artifact'
  sourceTool: 'code_interpreter' | 'image_generation' | 'math_modeling_agent'
}

export interface AgentResult {
  text: string
  artifacts: AgentArtifact[]
  backend: 'math_modeling_agent' | 'openai'
  mode: Exclude<AgentMode, 'auto'>
  runId?: string
  quality?: {
    total?: number
    threshold?: number
    passed?: boolean
    grade?: string
  }
  visualization: {
    intent: 'none' | 'data_plot' | 'diagram' | 'generative_image' | 'hybrid'
    phase: 'none' | 'exploration' | 'analysis' | 'validation' | 'publication' | 'presentation'
    requestedTools: string[]
    usedTools: Array<'code_interpreter' | 'image_generation' | 'math_modeling_agent'>
    rationale: string
    warnings: string[]
  }
}
