/// <reference types="vite/client" />

declare const __API_URL__: string
declare const __COLLAB_URL__: string

interface UpdateState {
  status: 'idle' | 'checking' | 'available' | 'downloading' | 'downloaded' | 'current' | 'error' | 'unsupported'
  version?: string
  percent?: number
  message?: string
}

interface Window {
  desktop?: {
    platform: string
    openExternal: (url: string) => Promise<void>
    getUpdateState: () => Promise<UpdateState>
    checkForUpdates: () => Promise<UpdateState>
    installUpdate: () => Promise<void>
    agentRequest: (request: {
      path: string
      method: string
      headers: Record<string, string>
      bodyBase64?: string
    }) => Promise<{
      ok: boolean
      status: number
      headers: Record<string, string>
      bodyBase64: string
    }>
    onUpdateState: (callback: (state: UpdateState) => void) => () => void
    onAuthTicket: (callback: (ticket: string) => void) => () => void
  }
}
