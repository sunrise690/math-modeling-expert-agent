import { useEffect, useState } from 'react'
import { ArrowRight, FileCode2, KeyRound, Laptop2, Users, WandSparkles } from 'lucide-react'
import { api } from '../lib/api'
import type { AuthPayload } from '../lib/types'

interface Props {
  onAuthenticated: (payload: AuthPayload) => void
}

export function Login({ onAuthenticated }: Props) {
  const [team, setTeam] = useState({ enabled: false, name: '内部团队', accessCodeRequired: true })
  const [displayName, setDisplayName] = useState('')
  const [accessCode, setAccessCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.authProviders().then(({ team: provider }) => setTeam(provider)).catch(() => setError('无法连接服务端，请先启动协作服务。'))
  }, [])

  const teamLogin = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!displayName.trim() || (team.accessCodeRequired && !accessCode)) return
    setBusy(true)
    setError('')
    try {
      onAuthenticated(await api.teamLogin(displayName.trim(), accessCode))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '登录失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand brand-inverse"><span className="brand-mark">Q</span><span>Qilintex</span></div>
        <div className="login-statement">
          <p className="folio">LaTeX 协作工作台</p>
          <h1>建模、写作、协作。<br />一个工作区。</h1>
          <p>统一管理项目、LaTeX 编辑、PDF 编译与 AI 辅助。</p>
        </div>
        <div className="capability-grid">
          <div><Users size={18} /><span>实时协作</span></div>
          <div><FileCode2 size={18} /><span>LaTeX / PDF</span></div>
          <div><WandSparkles size={18} /><span>AI 辅助</span></div>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <div className="pass-card-head">
            <span className="pass-number">01</span>
            <div><p className="eyebrow">登录</p><span>{team.name}</span></div>
          </div>
          <h2>进入工作区</h2>
          <p className="muted">输入名称{team.accessCodeRequired ? '和团队口令' : ''}即可继续。</p>

          <form className="team-login" onSubmit={teamLogin}>
            <label htmlFor="displayName">你的名称</label>
            <input id="displayName" autoComplete="name" autoFocus value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="用于协作光标和成员列表" maxLength={24} />
            {team.accessCodeRequired && <>
              <label htmlFor="accessCode">团队口令</label>
              <input id="accessCode" type="password" autoComplete="current-password" value={accessCode} onChange={(event) => setAccessCode(event.target.value)} placeholder="向团队负责人获取" maxLength={128} />
            </>}
            <button className="team-login-button" type="submit" disabled={busy || !team.enabled || !displayName.trim() || (team.accessCodeRequired && !accessCode)}>
              <span>{busy ? '正在进入…' : team.enabled ? '进入' : '登录未配置'}</span><ArrowRight size={18} />
            </button>
          </form>

          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="login-facts" aria-label="登录说明">
            <span><Laptop2 size={15} />会话保存在本机</span>
            <span><KeyRound size={15} />口令仅发送到团队服务端</span>
          </div>
        </div>
      </section>
    </main>
  )
}
