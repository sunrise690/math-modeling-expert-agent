import { useRef, useState } from 'react'
import { AtSign, Check, ImagePlus, Mail, Pencil, ShieldCheck, UserRound, X } from 'lucide-react'
import { api } from '../lib/api'
import type { User } from '../lib/types'
import { Avatar } from './FriendsPanel'

interface Props {
  user: User
  onClose: () => void
  onUpdated: (user: User) => void
}

const providerNames: Record<User['provider'], string> = {
  team: '团队账号',
  qq: 'QQ 登录',
  wechat: '微信登录',
  dev: '开发账号'
}

export function ProfilePanel({ user, onClose, onUpdated }: Props) {
  const [editing, setEditing] = useState(false)
  const [displayName, setDisplayName] = useState(user.displayName)
  const [email, setEmail] = useState(user.email || '')
  const [avatarUrl, setAvatarUrl] = useState(user.avatarUrl || '')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const avatarInput = useRef<HTMLInputElement>(null)

  const loadAvatar = (files: FileList | null) => {
    const file = files?.[0]
    if (!file) return
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      setMessage('头像仅支持 PNG、JPEG 或 WebP。')
      return
    }
    if (file.size > 500 * 1024) {
      setMessage('头像不能超过 500 KB。')
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      setAvatarUrl(String(reader.result || ''))
      setMessage('')
    }
    reader.readAsDataURL(file)
  }

  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!displayName.trim()) return
    setBusy(true)
    setMessage('')
    try {
      const { user: next } = await api.updateProfile({ displayName: displayName.trim(), email: email.trim(), avatarUrl })
      onUpdated(next)
      setEditing(false)
      setMessage('个人资料已更新。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '个人资料更新失败。')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="settings-backdrop profile-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="profile-panel" role="dialog" aria-modal="true" aria-label="个人资料" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div><p className="eyebrow">账户</p><h2>个人资料</h2></div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭个人资料"><X size={19} /></button>
        </header>

        <div className="profile-hero">
          <div className="profile-avatar"><Avatar user={{ ...user, avatarUrl }} /><button type="button" onClick={() => avatarInput.current?.click()} disabled={!editing || busy} aria-label="更换头像"><ImagePlus size={15} /></button></div>
          <div><h3>{user.displayName}</h3><span>@{user.handle}</span><small>{providerNames[user.provider]}</small></div>
          {!editing && <button type="button" className="secondary-button" onClick={() => setEditing(true)}><Pencil size={14} />编辑</button>}
          <input ref={avatarInput} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(event) => loadAvatar(event.target.files)} />
        </div>

        {editing ? (
          <form className="profile-form" onSubmit={save}>
            <label htmlFor="profileDisplayName">昵称</label>
            <div className="profile-input"><UserRound size={15} /><input id="profileDisplayName" value={displayName} onChange={(event) => setDisplayName(event.target.value)} maxLength={32} disabled={busy} /></div>
            <label htmlFor="profileEmail">邮箱</label>
            <div className="profile-input"><Mail size={15} /><input id="profileEmail" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="可选" disabled={busy} /></div>
            <label htmlFor="profileAvatarUrl">头像地址</label>
            <div className="profile-input"><ImagePlus size={15} /><input id="profileAvatarUrl" type="url" value={avatarUrl.startsWith('data:') ? '' : avatarUrl} onChange={(event) => setAvatarUrl(event.target.value)} placeholder={avatarUrl.startsWith('data:') ? '已选择本地头像' : 'https://…'} disabled={busy || avatarUrl.startsWith('data:')} /></div>
            {avatarUrl.startsWith('data:') && <button type="button" className="profile-clear-avatar" onClick={() => setAvatarUrl('')}>移除已选择的头像</button>}
            <footer><button type="button" className="secondary-button" onClick={() => setEditing(false)} disabled={busy}>取消</button><button type="submit" className="compile-button" disabled={busy || !displayName.trim()}><Check size={14} />保存</button></footer>
          </form>
        ) : (
          <div className="profile-facts">
            <div><AtSign size={16} /><span><small>账号 ID</small><strong>@{user.handle}</strong></span></div>
            <div><Mail size={16} /><span><small>邮箱</small><strong>{user.email || '未设置'}</strong></span></div>
            <div><ShieldCheck size={16} /><span><small>登录方式</small><strong>{providerNames[user.provider]}</strong></span></div>
          </div>
        )}
        {message && <p className={message.includes('已更新') ? 'profile-message success' : 'profile-message'}>{message}</p>}
      </section>
    </div>
  )
}
