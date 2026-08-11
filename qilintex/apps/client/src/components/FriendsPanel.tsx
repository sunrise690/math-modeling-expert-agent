import { useEffect, useState } from 'react'
import { Check, Search, UserPlus, Users } from 'lucide-react'
import { api } from '../lib/api'
import type { FriendsPayload, User } from '../lib/types'

export function FriendsPanel() {
  const [data, setData] = useState<FriendsPayload>({ friends: [], requests: [] })
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<User[]>([])
  const [message, setMessage] = useState('')

  const refresh = () => api.friends().then(setData)
  useEffect(() => { refresh().catch(() => undefined) }, [])

  const search = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!query.trim()) return
    const payload = await api.searchUsers(query.trim())
    setResults(payload.users)
    setMessage(payload.users.length ? '' : '没有找到匹配的用户。')
  }

  const request = async (userId: string) => {
    await api.requestFriend(userId)
    setResults((current) => current.filter((item) => item.id !== userId))
    setMessage('好友申请已发送。')
    await refresh()
  }

  const accept = async (requestId: string) => {
    await api.acceptFriend(requestId)
    await refresh()
  }

  const incoming = data.requests.filter((item) => item.direction === 'incoming')

  return (
    <div className="resource-panel friends-panel">
      <header className="resource-header">
        <div><p className="eyebrow">联系人</p><h2>好友</h2></div>
        <span className="large-count">{String(data.friends.length).padStart(2, '0')}</span>
      </header>

      <form className="friend-search" onSubmit={search}>
        <Search size={18} />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索名称或用户号" aria-label="搜索用户" />
        <button type="submit">搜索</button>
      </form>

      {message && <p className="inline-message">{message}</p>}
      {results.length > 0 && (
        <section className="friend-section">
          <h3>搜索结果</h3>
          {results.map((user) => (
            <div className="person-row" key={user.id}>
              <Avatar user={user} />
              <div className="person-copy"><strong>{user.displayName}</strong><span>@{user.handle}</span></div>
              <button className="icon-button" onClick={() => request(user.id)} aria-label={`添加 ${user.displayName}`}><UserPlus size={18} /></button>
            </div>
          ))}
        </section>
      )}

      {incoming.length > 0 && (
        <section className="friend-section">
          <h3>好友申请</h3>
          {incoming.map((item) => (
            <div className="person-row" key={item.id}>
              <Avatar user={item.user} />
              <div className="person-copy"><strong>{item.user.displayName}</strong><span>@{item.user.handle}</span></div>
              <button className="icon-button accept" onClick={() => accept(item.id)} aria-label="接受申请"><Check size={18} /></button>
            </div>
          ))}
        </section>
      )}

      <section className="friend-section">
        <h3>我的好友</h3>
        {data.friends.length === 0 ? (
          <div className="empty-resource"><Users size={30} /><p>还没有好友。搜索用户号即可发送申请。</p></div>
        ) : data.friends.map((user) => (
          <div className="person-row" key={user.id}>
            <Avatar user={user} />
            <div className="person-copy"><strong>{user.displayName}</strong><span>@{user.handle}</span></div>
          </div>
        ))}
      </section>
    </div>
  )
}

export function Avatar({ user, small = false }: { user: User; small?: boolean }) {
  if (user.avatarUrl) return <img className={`avatar${small ? ' small' : ''}`} src={user.avatarUrl} alt="" referrerPolicy="no-referrer" />
  return <span className={`avatar avatar-fallback${small ? ' small' : ''}`}>{user.displayName.slice(0, 1).toUpperCase()}</span>
}
