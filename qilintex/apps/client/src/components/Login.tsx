import { useEffect, useState } from 'react'
import { ArrowRight, Bot, Files, GitBranch, KeyRound, Search, Settings, ShieldCheck, Users } from 'lucide-react'
import { api } from '../lib/api'
import type { AuthPayload } from '../lib/types'

interface Props {
  onAuthenticated: (payload: AuthPayload) => void
}

export function Login({ onAuthenticated }: Props) {
  const [team, setTeam] = useState({ enabled: false, name: '内部团队', accessCodeRequired: true })
  const [accountId, setAccountId] = useState('')
  const [email, setEmail] = useState('')
  const [accessCode, setAccessCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.authProviders().then(({ team: provider }) => setTeam(provider)).catch(() => setError('无法连接服务端，请先启动协作服务。'))
  }, [])

  const teamLogin = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!accountId.trim() || (team.accessCodeRequired && !accessCode)) return
    setBusy(true)
    setError('')
    try {
      onAuthenticated(await api.teamLogin(accountId.trim().toLocaleLowerCase(), accessCode, email.trim()))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '登录失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-page">
      <header className="welcome-titlebar">
        <img src="./app-icon.jpg" alt="" />
        <span>数模工作台</span>
        <strong>Agent + QilinTeX</strong>
      </header>

      <nav className="welcome-activity" aria-label="工作台预览">
        <span className="active"><Files size={22} /></span>
        <span><Search size={22} /></span>
        <span><GitBranch size={22} /></span>
        <span><Bot size={22} /></span>
        <i />
        <span><Settings size={21} /></span>
      </nav>

      <section className="login-story">
        <div className="brand brand-inverse">
          <img className="brand-mark" src="./app-icon.jpg" alt="" />
          <span className="brand-copy"><strong>数模工作台</strong><small>Agent · QilinTeX</small></span>
        </div>
        <div className="login-statement">
          <h1>建模 写作 协作</h1>
          <p>从一个工作区开始</p>
        </div>
        <div className="welcome-shortcuts">
          <p>工作区能力</p>
          <div><Bot size={16} /><span><strong>数模 Agent</strong><small>拆题 选模 求解</small></span></div>
          <div><Files size={16} /><span><strong>QilinTeX</strong><small>项目文件 PDF 编译</small></span></div>
          <div><Users size={16} /><span><strong>实时协作</strong><small>多人编辑 私信 邮件</small></span></div>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <div className="pass-card-head">
            <span className="pass-number">›_</span>
            <div><p className="eyebrow">打开工作区</p><span>{team.name}</span></div>
          </div>
          <h2>登录</h2>
          <p className="muted">一个 ID 对应一个账号</p>

          <form className="team-login" onSubmit={teamLogin}>
            <label htmlFor="accountId">账号 ID</label>
            <input id="accountId" autoComplete="username" autoCapitalize="none" spellCheck={false} autoFocus value={accountId} onChange={(event) => setAccountId(event.target.value.toLocaleLowerCase())} placeholder="例如 zhangsan（全站唯一）" minLength={3} maxLength={24} pattern="[a-z0-9][a-z0-9_-]{2,23}" title="3–24 位小写字母、数字、下划线或连字符" />
            <label htmlFor="email">邮箱（可选）</label>
            <input id="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="供好友向你发送邮件" maxLength={254} />
            {team.accessCodeRequired && <>
              <label htmlFor="accessCode">团队口令</label>
              <input id="accessCode" type="password" autoComplete="current-password" value={accessCode} onChange={(event) => setAccessCode(event.target.value)} placeholder="向团队负责人获取" maxLength={128} />
            </>}
            <button className="team-login-button" type="submit" disabled={busy || !team.enabled || !accountId.trim() || (team.accessCodeRequired && !accessCode)}>
              <span>{busy ? '正在进入…' : team.enabled ? '进入' : '登录未配置'}</span><ArrowRight size={18} />
            </button>
          </form>

          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="login-facts" aria-label="登录说明">
            <span><ShieldCheck size={15} />一个 ID 对应一个账号</span>
            <span><KeyRound size={15} />口令仅发送到团队服务端</span>
          </div>
        </div>
      </section>
    </main>
  )
}
