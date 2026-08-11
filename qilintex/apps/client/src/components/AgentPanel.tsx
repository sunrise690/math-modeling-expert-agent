import { useState } from 'react'
import { ArrowUp, Copy, Download, ImageIcon, LoaderCircle, X } from 'lucide-react'
import { api } from '../lib/api'
import type { AgentResult } from '../lib/types'

interface Props {
  projectId: string
  source: string
  onClose: () => void
}

export function AgentPanel({ projectId, source, onClose }: Props) {
  const [message, setMessage] = useState('')
  const [result, setResult] = useState<AgentResult | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!message.trim()) return
    setBusy(true)
    setError('')
    setResult(null)
    try {
      setResult(await api.askAgent(projectId, source, message.trim()))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'AI 助手暂时不可用。')
    } finally {
      setBusy(false)
    }
  }

  return (
    <aside className="agent-panel">
      <header>
        <div><p className="eyebrow">main.tex</p><h2>AI 助手</h2></div>
        <button className="icon-button" onClick={onClose} aria-label="关闭"><X size={19} /></button>
      </header>
      <p className="agent-context">读取当前文档，不会自动修改。</p>

      <div className="agent-answer" aria-live="polite">
        {busy ? <div className="agent-loading"><LoaderCircle size={20} className="spin" />正在分析文档与绘图需求…</div> : result ? (
          <>
            {result.visualization.intent !== 'none' && (
              <div className="agent-tool-summary">
                <span>绘图路由</span>
                <strong>{result.visualization.usedTools.length
                  ? result.visualization.usedTools.map((tool) => tool === 'code_interpreter' ? '代码绘图' : 'Image').join(' + ')
                  : '仅规划'}</strong>
                <p>{result.visualization.rationale}</p>
              </div>
            )}
            {result.text && <pre>{result.text}</pre>}
            {result.artifacts.length > 0 && (
              <div className="agent-artifacts">
                {result.artifacts.map((artifact) => {
                  const href = `data:${artifact.mimeType};base64,${artifact.base64}`
                  return (
                    <article key={artifact.id}>
                      {artifact.mimeType.startsWith('image/')
                        ? <img src={href} alt={artifact.name} />
                        : <div className="agent-file-placeholder"><ImageIcon size={22} /><span>矢量图文件</span></div>}
                      <footer>
                        <div><strong>{artifact.name}</strong><small>{artifact.kind === 'data_figure' ? '可复现图形' : '生成式图片'}</small></div>
                        <a href={href} download={artifact.name} aria-label={`下载 ${artifact.name}`}><Download size={15} /></a>
                      </footer>
                    </article>
                  )
                })}
              </div>
            )}
            {result.visualization.warnings.map((warning) => <p className="agent-warning" key={warning}>{warning}</p>)}
            {result.text && <button className="copy-button" onClick={() => navigator.clipboard.writeText(result.text)}><Copy size={15} />复制回复</button>}
          </>
        ) : (
          <div className="agent-empty"><span className="large-count">AI</span><p>检查 LaTeX、生成公式与表格，或协调统计图、结构图和插画。</p></div>
        )}
        {error && <p className="form-error">{error}</p>}
      </div>

      <form className="agent-input" onSubmit={submit}>
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="输入对当前文档的要求" rows={4} />
        <button type="submit" disabled={busy || !message.trim()} aria-label="发送"><ArrowUp size={18} /></button>
      </form>
    </aside>
  )
}
