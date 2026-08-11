import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Check, ChevronDown, Copy, Download, FileSpreadsheet, ImageIcon, LoaderCircle, Paperclip, Settings, Trash2, X } from 'lucide-react'
import { api } from '../lib/api'
import type { AgentMode, AgentResult, AgentUpload } from '../lib/types'

interface Props {
  projectId: string
  source: string
  surface: 'modeling' | 'paper'
  initialMessage?: string
  initialMode?: AgentMode
  onClose: () => void
  onOpenSettings: () => void
}

function fileSize(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${Math.ceil(value / 1024)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

export function AgentPanel({ projectId, source, surface, initialMessage = '', initialMode = 'auto', onClose, onOpenSettings }: Props) {
  const [message, setMessage] = useState(initialMessage)
  const [mode, setMode] = useState<AgentMode>(initialMode)
  const [result, setResult] = useState<AgentResult | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploads, setUploads] = useState<AgentUpload[]>([])
  const [showModes, setShowModes] = useState(false)
  const uploadRef = useRef<HTMLInputElement>(null)
  const uploadsRef = useRef<AgentUpload[]>([])
  const runActiveRef = useRef(false)

  const modeOptions: Array<{ id: AgentMode; label: string; detail: string }> = [
    { id: 'auto', label: '自动', detail: '根据要求选择工作方式' },
    { id: 'solver', label: '建模', detail: '拆题、选模与求解' },
    { id: 'cumcm', label: '整题交付', detail: '从赛题到论文的完整流程' },
    { id: 'paper', label: '论文', detail: '写作、改写与 LaTeX' },
    { id: 'reviewer', label: '质检', detail: '风险、证据与规范审查' }
  ]
  const selectedMode = modeOptions.find((item) => item.id === mode) || modeOptions[0]

  useEffect(() => {
    if (initialMessage) setMessage(initialMessage)
  }, [initialMessage])

  useEffect(() => setMode(initialMode), [initialMode])

  useEffect(() => { uploadsRef.current = uploads }, [uploads])

  useEffect(() => () => {
    if (runActiveRef.current) return
    for (const upload of uploadsRef.current) void api.deleteAgentFile(projectId, upload.id).catch(() => undefined)
  }, [projectId])

  const addFiles = async (files: FileList | null) => {
    if (!files?.length) return
    const available = Math.max(0, 10 - uploads.length)
    if (available === 0) {
      setError('一次最多提交 10 个附件。')
      return
    }
    setUploading(true)
    setError('')
    try {
      const next: AgentUpload[] = []
      for (const file of Array.from(files).slice(0, available)) {
        if (file.size > 25 * 1024 * 1024) throw new Error(`${file.name} 超过 25 MB。`)
        const payload = await api.uploadAgentFile(projectId, file)
        next.push({ ...payload.upload, inspection: payload.inspection })
      }
      setUploads((current) => [...current, ...next])
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '附件上传失败。')
    } finally {
      setUploading(false)
      if (uploadRef.current) uploadRef.current.value = ''
    }
  }

  const removeUpload = async (upload: AgentUpload) => {
    setUploads((current) => current.filter((item) => item.id !== upload.id))
    await api.deleteAgentFile(projectId, upload.id).catch(() => undefined)
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!message.trim() && uploads.length === 0) return
    setBusy(true)
    runActiveRef.current = true
    setError('')
    setResult(null)
    try {
      const prompt = message.trim() || '请分析已提交的数据文件，并给出可复现的建模方案与结论。'
      setResult(await api.askAgent(projectId, source, prompt, mode, uploads.map((item) => item.id)))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'AI 助手暂时不可用。')
    } finally {
      await Promise.allSettled(uploads.map((upload) => api.deleteAgentFile(projectId, upload.id)))
      setUploads([])
      runActiveRef.current = false
      setBusy(false)
    }
  }

  return (
    <aside className="agent-panel">
      <header>
        <div><p className="eyebrow">{surface === 'paper' ? 'QilinTeX · main.tex' : '当前数模项目'}</p><h2>数模 Agent</h2></div>
        <button className="icon-button" onClick={onClose} disabled={busy || uploading} aria-label="关闭"><X size={19} /></button>
      </header>
      <p className="agent-context">{surface === 'paper'
        ? '读取当前论文并调用建模、检索、计算与论文质检能力；不会自动修改正文。'
        : '在当前项目中执行拆题、选模、求解、绘图与质量检查，结果与论文工作区共享。'}</p>

      <div className="agent-answer" aria-live="polite">
        {busy ? <div className="agent-loading"><LoaderCircle size={20} className="spin" />正在分析文档与绘图需求…</div> : result ? (
          <>
            <div className="agent-tool-summary">
              <span>执行后端</span>
              <strong>{result.backend === 'math_modeling_agent' ? '数模 Agent' : 'OpenAI 直连'}</strong>
              <p>{({ solver: '建模', cumcm: '整题交付', paper: '论文', reviewer: '质检' } as const)[result.mode]}
                {typeof result.quality?.total === 'number' ? ` · 质量 ${result.quality.total}/${result.quality.threshold ?? 100}` : ''}
              </p>
            </div>
            {result.visualization.intent !== 'none' && (
              <div className="agent-tool-summary">
                <span>绘图路由</span>
                <strong>{result.visualization.usedTools.length
                  ? result.visualization.usedTools.map((tool) => tool === 'code_interpreter' ? '代码绘图' : tool === 'image_generation' ? 'Image' : '数模 Agent').join(' + ')
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
                        <div><strong>{artifact.name}</strong><small>{artifact.kind === 'data_figure' ? '可复现图形' : artifact.kind === 'generated_image' ? '生成式图片' : '数模 Agent 产物'}</small></div>
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
          <div className="agent-empty"><span className="large-count">AI</span><p>拆题选模、推导公式、检查论文，或调用工具生成可复现结果与图件。</p></div>
        )}
        {error && <div className="agent-error"><p className="form-error">{error}</p>{/Codex|模型|API|登录|配置/.test(error) && <button type="button" className="secondary-button" onClick={onOpenSettings}><Settings size={14} />打开模型设置</button>}</div>}
      </div>

      <form className="agent-input" onSubmit={submit}>
        <div className="agent-mode-picker">
          <button type="button" className="agent-mode-trigger" onClick={() => setShowModes((value) => !value)} disabled={busy} aria-expanded={showModes}>
            <span><small>工作模式</small><strong>{selectedMode.label}</strong></span><ChevronDown size={14} />
          </button>
          {showModes && <div className="agent-mode-menu" role="menu">
            {modeOptions.map((option) => <button type="button" role="menuitem" key={option.id} className={option.id === mode ? 'active' : ''} onClick={() => { setMode(option.id); setShowModes(false) }}>
              <span><strong>{option.label}</strong><small>{option.detail}</small></span>{option.id === mode && <Check size={14} />}
            </button>)}
          </div>}
        </div>
        {uploads.length > 0 && <div className="agent-upload-list" aria-label="待提交附件">
          {uploads.map((upload) => <div key={upload.id}>
            <FileSpreadsheet size={15} />
            <span><strong>{upload.name}</strong><small>{fileSize(upload.size)}</small></span>
            <button type="button" onClick={() => { void removeUpload(upload) }} disabled={busy} aria-label={`移除 ${upload.name}`}><Trash2 size={13} /></button>
          </div>)}
        </div>}
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="输入建模、论文或质检要求" rows={4} />
        <div className="agent-input-actions">
          <button type="button" className="agent-attach" onClick={() => uploadRef.current?.click()} disabled={busy || uploading || uploads.length >= 10} aria-label="添加数据附件" title="添加数据附件">
            {uploading ? <LoaderCircle className="spin" size={16} /> : <Paperclip size={16} />}
          </button>
          <span>CSV · TSV · XLSX · JSON，单个 25 MB</span>
          <button className="agent-send" type="submit" disabled={busy || uploading || (!message.trim() && uploads.length === 0)} aria-label="发送"><ArrowUp size={18} /></button>
        </div>
        <input ref={uploadRef} type="file" accept=".csv,.tsv,.xlsx,.json" multiple hidden onChange={(event) => { void addFiles(event.target.files) }} />
      </form>
    </aside>
  )
}
