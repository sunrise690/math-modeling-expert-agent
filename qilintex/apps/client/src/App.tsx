import { useEffect, useState } from 'react'
import { api, getAuthRealm, setAuthRealm, setToken } from './lib/api'
import type { AuthPayload, User } from './lib/types'
import { Login } from './components/Login'
import { Workbench } from './components/Workbench'
import { realmFromHash, sessionFromHash } from './lib/urls'

export default function App() {
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

  if (loading) return <div className="boot-screen"><span className="brand-mark">Q</span><p>正在连接</p></div>
  if (!user) return <Login onAuthenticated={authenticated} />
  return <Workbench user={user} onLogout={() => setUser(null)} />
}
