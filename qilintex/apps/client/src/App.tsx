import { useEffect, useState } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'
import { api, getAuthRealm, setAuthRealm, setToken } from './lib/api'
import type { AuthPayload, User } from './lib/types'
import { Login } from './components/Login'
import { Landing } from './components/Landing'
import { Workbench } from './components/Workbench'
import { realmFromHash, sessionFromHash } from './lib/urls'

export default function App() {
  useRegisterSW({ immediate: true })
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [showLogin, setShowLogin] = useState(Boolean(window.desktop))

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
      ? showLogin
        ? <Login onAuthenticated={authenticated} />
        : <Landing onUseOnline={() => setShowLogin(true)} />
      : <Workbench user={user} onUserChanged={setUser} onLogout={() => setUser(null)} />

  return content
}
