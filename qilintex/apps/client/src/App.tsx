import { useEffect, useState } from 'react'
import { Download } from 'lucide-react'
import { useRegisterSW } from 'virtual:pwa-register/react'
import { api, getAuthRealm, setAuthRealm, setToken } from './lib/api'
import type { AuthPayload, User } from './lib/types'
import { Login } from './components/Login'
import { Workbench } from './components/Workbench'
import { realmFromHash, sessionFromHash } from './lib/urls'

export default function App() {
  useRegisterSW({ immediate: true })
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const authenticated = (payload: AuthPayload) => {
    setAuthRealm(payload.realm)
    if (payload.token) setToken(payload.token, payload.realm)
    setUser(payload.user)
  }

  useEffect(() => {
    const webToken = sessionFromHash(location.hash)
    if (webToken) {
      const realm = realmFromHash(location.hash)
      setAuthRealm(realm)
      setToken(webToken, realm)
      history.replaceState({}, '', `${location.pathname}${location.search}`)
    }

    api.me(getAuthRealm()).then(authenticated).catch(() => setUser(null)).finally(() => setLoading(false))

    if (!window.desktop) return
    return window.desktop.onAuthTicket(async (ticket) => {
      try {
        authenticated(await api.exchangeTicket(ticket))
      } finally {
        setLoading(false)
      }
    })
  }, [])

  const content = loading
    ? <div className="boot-screen"><img className="brand-mark" src="./app-icon.jpg" alt="" /><p>正在连接工作台…</p></div>
    : !user
      ? <Login onAuthenticated={authenticated} />
      : <Workbench user={user} onUserChanged={setUser} onLogout={() => setUser(null)} />

  return <>
    {content}
    {!window.desktop && <a className="app-download-rail" href="/downloads/Qilintex-Setup-0.1.0-x64.exe" aria-label="下载 Qilintex Windows App">
      <Download size={17} />
      <span><strong>下载 App</strong><small>本机 Codex 与 API</small></span>
    </a>}
  </>
}
