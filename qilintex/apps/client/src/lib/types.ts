export type AuthRealm = 'team' | 'oauth'

export interface User {
  id: string
  handle: string
  displayName: string
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

export interface AgentArtifact {
  id: string
  name: string
  mimeType: string
  base64: string
  kind: 'data_figure' | 'generated_image'
  sourceTool: 'code_interpreter' | 'image_generation'
}

export interface AgentResult {
  text: string
  artifacts: AgentArtifact[]
  visualization: {
    intent: 'none' | 'data_plot' | 'diagram' | 'generative_image' | 'hybrid'
    phase: 'none' | 'exploration' | 'analysis' | 'validation' | 'publication' | 'presentation'
    requestedTools: string[]
    usedTools: Array<'code_interpreter' | 'image_generation'>
    rationale: string
    warnings: string[]
  }
}
