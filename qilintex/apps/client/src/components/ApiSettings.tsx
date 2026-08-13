import { useEffect, useMemo, useState } from 'react'
import { Check, ExternalLink, KeyRound, LoaderCircle, LogIn, MonitorCog, PlugZap, X } from 'lucide-react'
import { api } from '../lib/api'
import type { AgentConfig, AgentProviderOption, CodexLoginSession } from '../lib/types'

interface Props {
  onClose: () => void
  onSaved: (message: string) => void
}

function optionById(config: AgentConfig | null, id: string) {
  return config?.providerCatalog.find((item) => item.id === id)
}

export function ApiSettings({ onClose, onSaved }: Props) {
  const [config, setConfig] = useState<AgentConfig | null>(null)
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [reasoningEffort, setReasoningEffort] = useState('medium')
  const [runtimeReady, setRuntimeReady] = useState(false)
  const [status, setStatus] = useState<{ text: string; tone: 'normal' | 'success' | 'error' }>({ text: '正在连接本机运行器…', tone: 'normal' })
  const [busy, setBusy] = useState(false)
  const [login, setLogin] = useState<CodexLoginSession | null>(null)

  const applyOption = (option: AgentProviderOption) => {
    setProvider(option.id)
    setModel(option.profile.model || option.defaultModel || '')
    setBaseUrl(option.profile.baseUrl || option.defaultBaseUrl || '')
    setApiKey('')
    setReasoningEffort(option.profile.reasoningEffort || 'medium')
  }

  const loadConfig = async (announce = false) => {
    const payload = await api.agentConfig()
    setRuntimeReady(true)
    setConfig(payload)
    const active = optionById(payload, payload.activeProvider) || payload.providerCatalog[0]
    if (active) applyOption(active)
    const codexReady = Boolean(payload.codexStatus?.authenticated || payload.codexStatus?.available)
    setStatus({
      text: announce && codexReady
        ? '浏览器确认完成，已登录本机 Codex。'
        : codexReady
          ? '配置只保存在这台电脑上，调用使用你自己的网络。'
          : '点击 Codex 登录，在浏览器确认后会自动完成。',
      tone: announce && codexReady ? 'success' : 'normal'
    })
    return payload
  }

  useEffect(() => {
    loadConfig().catch((error) => {
      setRuntimeReady(false)
      setStatus({ text: error instanceof Error ? error.message : '无法连接本机运行器。', tone: 'error' })
    })
  }, [])

  useEffect(() => {
    if (!login || login.status !== 'pending') return
    const timer = window.setInterval(async () => {
      try {
        const { login: next } = await api.codexLoginStatus(login.id)
        setLogin(next)
        if (next.status === 'completed') {
          window.clearInterval(timer)
          await loadConfig(true)
        } else if (next.status !== 'pending') {
          window.clearInterval(timer)
          setStatus({ text: next.message || 'Codex 登录未完成。', tone: 'error' })
        }
      } catch {
        // 本机登录进程仍可能正常运行，短暂轮询失败不主动取消。
      }
    }, 1500)
    return () => window.clearInterval(timer)
  }, [login?.id, login?.status])

  const selected = useMemo(() => optionById(config, provider), [config, provider])
  const codexReady = Boolean(config?.codexStatus?.authenticated || config?.codexStatus?.available)
  const payload = () => ({ provider, model: model.trim(), baseUrl: baseUrl.trim(), apiKey: apiKey.trim(), reasoningEffort })

  const startCodexLogin = async () => {
    const popup = window.desktop ? null : window.open('about:blank', 'qilintex-codex-login', 'popup,width=760,height=720')
    setBusy(true)
    setStatus({ text: '正在启动本机 Codex 登录…', tone: 'normal' })
    try {
      const { login: next } = await api.startCodexLogin()
      setLogin(next)
      const target = next.mode === 'device-code' ? next.verificationUrl : next.authUrl
      if (target && window.desktop) await window.desktop.openExternal(target)
      else if (popup && target) popup.location.href = target
      else if (target) window.open(target, '_blank', 'noopener,noreferrer')
      setStatus({ text: next.mode === 'device-code' ? `请在浏览器输入验证码 ${next.userCode}` : '请在浏览器确认登录，完成后此处会自动更新。', tone: 'normal' })
    } catch (error) {
      popup?.close()
      setStatus({ text: error instanceof Error ? error.message : '无法启动 Codex 登录。', tone: 'error' })
    } finally {
      setBusy(false)
    }
  }

  const test = async () => {
    setBusy(true)
    setStatus({ text: '正在使用本机网络测试连接…', tone: 'normal' })
    try {
      const { test: result } = await api.testAgentConfig(payload())
      if (!result.ok) throw new Error(result.reason || '连接测试失败。')
      setStatus({ text: `连接成功${result.latencyMs ? ` · ${result.latencyMs} ms` : ''}`, tone: 'success' })
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : '连接测试失败。', tone: 'error' })
    } finally {
      setBusy(false)
    }
  }

  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      const { config: next } = await api.saveAgentConfig(payload())
      setConfig(next)
      setApiKey('')
      setStatus({ text: '已加密保存在当前电脑。', tone: 'success' })
      onSaved('本机模型与 API 配置已更新。')
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : '保存失败。', tone: 'error' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="settings-backdrop" role="presentation" onMouseDown={onClose}>
      <form className="api-settings" onSubmit={save} onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div><p className="eyebrow">本机设置</p><h2>模型与 API</h2><span>登录、密钥、模型调用均属于当前电脑用户。</span></div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭模型与 API 设置"><X size={19} /></button>
        </header>

        {!runtimeReady ? (
          <section className="local-runtime-empty">
            <MonitorCog size={28} />
            <div><h3>本机 Agent 未连接</h3><p>{status.text}</p><small>在线项目、论文编辑与协作不受影响；模型登录、密钥和本机计算不会转交给协作服务器。</small></div>
          </section>
        ) : (
          <>
            <div className="api-settings-body">
              <nav className="provider-switch" aria-label="模型通道">
                {config?.providerCatalog.map((option) => (
                  <button type="button" key={option.id} className={provider === option.id ? 'active' : ''} onClick={() => applyOption(option)} disabled={busy || config.configLocked}>
                    <span><strong>{option.label}</strong><small>{option.description}</small></span>
                    {provider === option.id && <Check size={15} />}
                  </button>
                ))}
              </nav>
              <section className="api-fields">
                <div className={`api-route ${status.tone}`}><PlugZap size={16} /><span>{status.text}</span></div>
                {selected?.id === 'codex-cli' && !codexReady && (!login || login.status !== 'pending') && (
                  <button type="button" className="codex-login-card" onClick={() => { void startCodexLogin() }} disabled={busy || config?.configLocked}>
                    <LogIn size={18} />
                    <span><strong>登录本机 Codex</strong><small>点击后在浏览器确认，随后自动登录</small></span>
                    <ExternalLink size={15} />
                  </button>
                )}
                {selected?.id === 'codex-cli' && login?.status === 'pending' && (
                  <div className="codex-login-session">
                    <div><LoaderCircle className="spin" size={17} /><span><strong>等待浏览器确认</strong><small>{login.mode === 'device-code' ? `验证码：${login.userCode}` : '确认后无需复制 localhost 地址，会自动完成。'}</small></span></div>
                  </div>
                )}
                {selected?.id === 'codex-cli' && (login?.status === 'completed' || codexReady) && <div className="codex-login-complete"><Check size={16} />本机 Codex 已登录</div>}
                <label htmlFor="agentModel">模型</label>
                <input id="agentModel" value={model} onChange={(event) => setModel(event.target.value)} placeholder="模型 ID" disabled={busy || config?.configLocked} list="agent-model-list" required />
                <datalist id="agent-model-list">{selected?.profile.models?.map((item) => <option key={item.id} value={item.id}>{item.displayName || item.id}</option>)}</datalist>
                {selected && selected.id !== 'codex-cli' && <>
                  <label htmlFor="agentBaseUrl">API Base URL</label>
                  <input id="agentBaseUrl" type="url" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder={selected.defaultBaseUrl || 'https://…/v1'} disabled={busy || config?.configLocked} required />
                </>}
                {selected?.requiresApiKey && <>
                  <label htmlFor="agentApiKey">API Key</label>
                  <div className="api-key-input"><KeyRound size={15} /><input id="agentApiKey" type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={selected.profile.apiKeyConfigured ? '已保存在本机；留空保持不变' : '粘贴 API Key'} disabled={busy || config?.configLocked} autoComplete="new-password" /></div>
                </>}
                <label htmlFor="reasoningEffort">推理强度</label>
                <select id="reasoningEffort" value={reasoningEffort} onChange={(event) => setReasoningEffort(event.target.value)} disabled={busy || config?.configLocked}>
                  <option value="low">低</option><option value="medium">中</option><option value="high">高</option><option value="xhigh">很高</option><option value="max">最高</option>
                </select>
              </section>
            </div>
            <footer>
              <span>{selected?.profile.apiKeyConfigured ? '密钥已由当前 Windows 用户加密保存' : selected?.requiresApiKey ? '密钥尚未保存在本机' : '该通道无需 API Key'}</span>
              <div><button className="secondary-button" type="button" onClick={() => { void test() }} disabled={busy || !selected || config?.configLocked || (selected.id === 'codex-cli' && !codexReady)}>{busy ? <LoaderCircle className="spin" size={14} /> : null}测试连接</button><button className="compile-button" type="submit" disabled={busy || !selected || config?.configLocked || (selected.id === 'codex-cli' && !codexReady)}>保存并使用</button></div>
            </footer>
          </>
        )}
      </form>
    </div>
  )
}
