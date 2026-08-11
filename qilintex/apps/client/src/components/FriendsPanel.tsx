import { useCallback, useEffect, useState } from 'react'
import { Check, Mail, MessageSquare, RefreshCw, Search, Send, UserPlus, Users, X } from 'lucide-react'
import { api } from '../lib/api'
import type { DirectMessage, FriendsPayload, User } from '../lib/types'

export function FriendsPanel({ currentUser }: { currentUser: User }) {
  const [data, setData] = useState<FriendsPayload>({ friends: [], requests: [] })
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<User[]>([])
  const [message, setMessage] = useState('')
  const [acceptingId, setAcceptingId] = useState('')
  const [activeFriend, setActiveFriend] = useState<User | null>(null)
  const [messages, setMessages] = useState<DirectMessage[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setData(await api.friends())
    } catch {
      setMessage('无法刷新好友列表，请检查网络连接。')
    }
  }, [])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => { void refresh() }, 5000)
    return () => window.clearInterval(timer)
  }, [refresh])

  useEffect(() => {
    if (!activeFriend) return
    const load = async () => setMessages((await api.directMessages(activeFriend.id)).messages)
    void load().catch((error) => setMessage(error instanceof Error ? error.message : '无法读取私信。'))
    const timer = window.setInterval(() => { void load().catch(() => undefined) }, 3000)
    return () => window.clearInterval(timer)
  }, [activeFriend?.id])

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
    setAcceptingId(requestId)
    try {
      await api.acceptFriend(requestId)
      setMessage('已接受好友申请。')
      await refresh()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '无法接受好友申请。')
    } finally {
      setAcceptingId('')
    }
  }

  const incoming = data.requests.filter((item) => item.direction === 'incoming')
  const outgoing = data.requests.filter((item) => item.direction === 'outgoing')

  const sendMessage = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!activeFriend || !draft.trim()) return
    setSending(true)
    try {
      const { message: sent } = await api.sendDirectMessage(activeFriend.id, draft.trim())
      setMessages((current) => [...current, sent])
      setDraft('')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '私信发送失败。')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="resource-panel friends-panel">
      <header className="resource-header">
        <div><p className="eyebrow">联系人</p><h2>好友</h2></div>
        <div className="friend-header-actions">
          <span className="large-count">{String(data.friends.length).padStart(2, '0')}</span>
          <button className="icon-button" type="button" onClick={() => { void refresh() }} aria-label="刷新好友和申请" title="刷新"><RefreshCw size={16} /></button>
        </div>
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

      <section className="friend-section">
        <h3>好友申请</h3>
        {incoming.length === 0 && outgoing.length === 0 ? (
          <div className="empty-resource"><Users size={26} /><p>暂无待处理申请。收到新申请后会自动显示在这里。</p></div>
        ) : (
          <>
            {incoming.map((item) => (
            <div className="person-row" key={item.id}>
              <Avatar user={item.user} />
              <div className="person-copy"><strong>{item.user.displayName}</strong><span>@{item.user.handle} · 向你发送了好友申请</span></div>
              <button className="icon-button accept" type="button" disabled={Boolean(acceptingId)} onClick={() => { void accept(item.id) }} aria-label={`接受 ${item.user.displayName} 的申请`} title="接受申请"><Check size={18} /></button>
            </div>
            ))}
            {outgoing.map((item) => (
              <div className="person-row" key={item.id}>
                <Avatar user={item.user} />
                <div className="person-copy"><strong>{item.user.displayName}</strong><span>@{item.user.handle} · 已发送，等待对方接受</span></div>
                <span className="request-status">等待中</span>
              </div>
            ))}
          </>
        )}
      </section>

      <section className="friend-section">
        <h3>我的好友</h3>
        {data.friends.length === 0 ? (
          <div className="empty-resource"><Users size={30} /><p>还没有好友。搜索用户号即可发送申请。</p></div>
        ) : data.friends.map((user) => (
          <div className="person-row" key={user.id}>
            <Avatar user={user} />
            <div className="person-copy"><strong>{user.displayName}</strong><span>@{user.handle}{user.email ? ` · ${user.email}` : ''}</span></div>
            <div className="person-actions">
              <button className="icon-button" type="button" onClick={() => setActiveFriend(user)} aria-label={`私信 ${user.displayName}`} title="私信"><MessageSquare size={17} /></button>
              {user.email
                ? <a className="icon-button" href={`mailto:${encodeURIComponent(user.email)}?subject=${encodeURIComponent('来自数模工作台的消息')}`} aria-label={`给 ${user.displayName} 发邮件`} title="用邮件客户端发邮件"><Mail size={17} /></a>
                : <button className="icon-button" type="button" disabled aria-label={`${user.displayName} 未填写邮箱`} title="该好友未填写邮箱"><Mail size={17} /></button>}
            </div>
          </div>
        ))}
      </section>

      {activeFriend && (
        <section className="direct-chat" aria-label={`与 ${activeFriend.displayName} 的私信`}>
          <header>
            <Avatar user={activeFriend} small />
            <div><strong>{activeFriend.displayName}</strong><span>@{activeFriend.handle}</span></div>
            {activeFriend.email && <a className="icon-button" href={`mailto:${encodeURIComponent(activeFriend.email)}`} title="发邮件" aria-label={`给 ${activeFriend.displayName} 发邮件`}><Mail size={16} /></a>}
            <button className="icon-button" type="button" onClick={() => setActiveFriend(null)} aria-label="关闭私信"><X size={17} /></button>
          </header>
          <div className="direct-messages" aria-live="polite">
            {messages.length === 0 ? <p>还没有消息，开始对话吧。</p> : messages.map((item) => (
              <article key={item.id} className={item.fromId === currentUser.id ? 'mine' : ''}>
                <p>{item.body}</p>
                <time dateTime={item.createdAt}>{new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(new Date(item.createdAt))}</time>
              </article>
            ))}
          </div>
          <form onSubmit={sendMessage}>
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="输入私信" rows={3} maxLength={2000} onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }} />
            <button type="submit" disabled={sending || !draft.trim()} aria-label="发送私信"><Send size={17} /></button>
          </form>
        </section>
      )}
    </div>
  )
}

export function Avatar({ user, small = false }: { user: User; small?: boolean }) {
  if (user.avatarUrl) return <img className={`avatar${small ? ' small' : ''}`} src={user.avatarUrl} alt="" referrerPolicy="no-referrer" />
  return <span className={`avatar avatar-fallback${small ? ' small' : ''}`}>{user.displayName.slice(0, 1).toUpperCase()}</span>
}
