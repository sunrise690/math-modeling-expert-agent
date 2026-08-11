import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BookOpenText, Bot, Check, ChevronRight, CircleAlert, FileCode2, FilePlus2, Files,
  LayoutDashboard, LogOut, Menu, PanelLeftClose, PanelLeftOpen, Play, Share2,
  Users, X
} from 'lucide-react'
import { api, setToken } from '../lib/api'
import type { CompileResult, Project, User } from '../lib/types'
import { AgentPanel } from './AgentPanel'
import { CollaborativeEditor } from './CollaborativeEditor'
import { Avatar, FriendsPanel } from './FriendsPanel'
import { ModelingDashboard } from './ModelingDashboard'
import { UpdateButton } from './UpdateButton'
import { invitationFromSearch } from '../lib/urls'

interface Props {
  user: User
  onLogout: () => void
}

type SyncState = 'connecting' | 'connected' | 'disconnected'
type Notice = { message: string; tone: 'success' | 'error' }

export function Workbench({ user, onLogout }: Props) {
  const [projects, setProjects] = useState<Project[]>([])
  const [activeId, setActiveId] = useState('')
  const [view, setView] = useState<'projects' | 'friends'>('projects')
  const [showCreate, setShowCreate] = useState(false)
  const [projectName, setProjectName] = useState('')
  const [source, setSource] = useState('')
  const [sync, setSync] = useState<SyncState>('connecting')
  const [collaborators, setCollaborators] = useState<User[]>([])
  const [compile, setCompile] = useState<CompileResult | null>(null)
  const [compiling, setCompiling] = useState(false)
  const [showAgent, setShowAgent] = useState(false)
  const [projectSurface, setProjectSurface] = useState<'modeling' | 'editor'>('modeling')
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > 760)
  const [split, setSplit] = useState(52)
  const [notice, setNotice] = useState<Notice | null>(null)
  const splitHost = useRef<HTMLDivElement>(null)

  const activeProject = projects.find((project) => project.id === activeId)
  const pdfUrl = useMemo(() => compile?.pdfBase64 ? `data:application/pdf;base64,${compile.pdfBase64}` : '', [compile?.pdfBase64])

  useEffect(() => {
    const load = async () => {
      const invite = invitationFromSearch(location.search)
      if (invite) {
        try {
          await api.acceptInvitation(invite)
          history.replaceState({}, '', location.pathname)
          setNotice({ message: '已加入协作项目。', tone: 'success' })
        } catch (error) {
          setNotice({ message: error instanceof Error ? error.message : '无法接受项目邀请。', tone: 'error' })
        }
      }
      const { projects: list } = await api.projects()
      setProjects(list)
      const fromUrl = new URLSearchParams(location.search).get('project')
      const saved = localStorage.getItem('tonggao.activeProject')
      const next = list.find((item) => item.id === fromUrl)?.id || list.find((item) => item.id === saved)?.id || list[0]?.id || ''
      setActiveId(next)
    }
    load().catch((error) => setNotice({ message: error.message, tone: 'error' }))
  }, [])

  useEffect(() => {
    if (activeId) localStorage.setItem('tonggao.activeProject', activeId)
    setCompile(null)
  }, [activeId])

  const createProject = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!projectName.trim()) return
    const { project } = await api.createProject(projectName.trim())
    setProjects((current) => [project, ...current])
    setActiveId(project.id)
    setProjectName('')
    setShowCreate(false)
    setView('projects')
  }

  const runCompile = async () => {
    if (!activeProject) return
    setCompiling(true)
    setCompile(null)
    try {
      setCompile(await api.compile(activeProject.id, source))
    } catch (reason) {
      setCompile({ ok: false, log: reason instanceof Error ? reason.message : '编译请求失败' })
    } finally {
      setCompiling(false)
    }
  }

  const share = async () => {
    if (!activeProject) return
    try {
      const { url } = await api.createInvitation(activeProject.id)
      await navigator.clipboard.writeText(url)
      setNotice({ message: '协作邀请链接已复制，7 天内有效。', tone: 'success' })
    } catch (error) {
      setNotice({ message: error instanceof Error ? error.message : '无法创建邀请链接。', tone: 'error' })
    }
    setTimeout(() => setNotice(null), 3000)
  }

  const copyModelingCommand = async (command: string, label: string) => {
    if (!activeProject) return
    const text = `$cumcm-modeling ${command} 当前项目“${activeProject.name}”`
    try {
      await navigator.clipboard.writeText(text)
      setNotice({ message: `已复制“${label}”命令。`, tone: 'success' })
    } catch {
      setNotice({ message: `复制失败，请手动运行：${text}`, tone: 'error' })
    }
    setTimeout(() => setNotice(null), 3000)
  }

  const logout = async () => {
    await api.logout().catch(() => undefined)
    setToken()
    onLogout()
  }

  const beginResize = (event: React.PointerEvent) => {
    const startX = event.clientX
    const startSplit = split
    const width = splitHost.current?.clientWidth || 1
    const move = (pointer: PointerEvent) => setSplit(Math.min(75, Math.max(30, startSplit + ((pointer.clientX - startX) / width) * 100)))
    const stop = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', stop)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', stop)
  }

  const resizeWithKeyboard = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    const step = event.shiftKey ? 10 : 2

    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault()
      setSplit((current) => Math.min(75, Math.max(30, current + (event.key === 'ArrowRight' ? step : -step))))
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault()
      setSplit(event.key === 'Home' ? 30 : 75)
    }
  }

  return (
    <div className={`app-shell${sidebarOpen ? '' : ' sidebar-collapsed'}`}>
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="brand"><span className="brand-mark">Q</span><span>Qilintex</span></div>
          <button className="icon-button sidebar-close" onClick={() => setSidebarOpen(false)} aria-label="收起侧栏"><PanelLeftClose size={19} /></button>
        </div>
        <nav className="primary-nav" aria-label="主导航">
          <button className={view === 'projects' ? 'active' : ''} onClick={() => setView('projects')}><Files size={18} /><span>项目</span><span className="nav-count">{projects.length}</span></button>
          <button className={view === 'friends' ? 'active' : ''} onClick={() => setView('friends')}><Users size={18} /><span>好友</span></button>
        </nav>

        <div className="sidebar-rule" />
        <div className="project-list-head"><span>我的项目</span><button onClick={() => setShowCreate(true)} aria-label="新建项目"><FilePlus2 size={17} /></button></div>
        <div className="project-list">
          {projects.map((project) => (
            <button key={project.id} className={activeId === project.id && view === 'projects' ? 'active' : ''} onClick={() => { setActiveId(project.id); setView('projects') }}>
              <FileCode2 size={17} /><span>{project.name}</span><ChevronRight size={15} />
            </button>
          ))}
          {projects.length === 0 && <p className="sidebar-empty">尚未创建项目</p>}
        </div>

        <div className="user-menu">
          <Avatar user={user} small />
          <div><strong>{user.displayName}</strong><span>@{user.handle}</span></div>
          <button className="icon-button" onClick={logout} aria-label="退出登录"><LogOut size={17} /></button>
        </div>
      </aside>

      <main className="workspace">
        <header className="workspace-bar">
          <div className="project-title">
            {!sidebarOpen && <button className="icon-button" onClick={() => setSidebarOpen(true)} aria-label="展开侧栏"><PanelLeftOpen size={19} /></button>}
            <span className="project-index">{activeProject ? String(projects.findIndex((item) => item.id === activeProject.id) + 1).padStart(2, '0') : '—'}</span>
            <div><strong>{view === 'friends' ? '好友' : activeProject?.name || '项目'}</strong><span>{view === 'friends' ? '联系人' : activeProject ? projectSurface === 'modeling' ? '流程' : 'main.tex' : '未选择项目'}</span></div>
          </div>
          {view === 'projects' && activeProject && (
            <div className="workspace-actions">
              {projectSurface === 'editor' && <div className={`sync-state ${sync}`}><span />{sync === 'connected' ? '已同步' : sync === 'connecting' ? '连接中' : '离线'}</div>}
              {projectSurface === 'editor' && (
                <div className="collaborator-stack" title={`${collaborators.length + 1} 人在线`}>
                  <Avatar user={user} small />
                  {collaborators.slice(0, 3).map((person) => <Avatar user={person} small key={person.id} />)}
                  {collaborators.length > 3 && <span className="avatar small avatar-more">+{collaborators.length - 3}</span>}
                </div>
              )}
              <div className="surface-switch" role="group" aria-label="项目视图">
                <button aria-pressed={projectSurface === 'modeling'} className={projectSurface === 'modeling' ? 'active' : ''} onClick={() => { setProjectSurface('modeling'); setShowAgent(false) }}><LayoutDashboard size={15} />流程</button>
                <button aria-pressed={projectSurface === 'editor'} className={projectSurface === 'editor' ? 'active' : ''} onClick={() => setProjectSurface('editor')}><BookOpenText size={15} />论文</button>
              </div>
              <UpdateButton />
              <button className="toolbar-button" onClick={share}><Share2 size={16} />分享</button>
              {projectSurface === 'editor' && <button className="toolbar-button" onClick={() => setShowAgent((current) => !current)}><Bot size={16} />AI</button>}
              {projectSurface === 'editor' && <button className="compile-button" onClick={runCompile} disabled={compiling}><Play size={16} />{compiling ? '编译中' : '编译'}</button>}
            </div>
          )}
          <button className="mobile-menu icon-button" onClick={() => setSidebarOpen((value) => !value)} aria-label="菜单"><Menu size={20} /></button>
        </header>

        {notice && <div className={`notice ${notice.tone}`} role="status" aria-live="polite">{notice.tone === 'success' ? <Check size={16} /> : <CircleAlert size={16} />}{notice.message}<button onClick={() => setNotice(null)} aria-label="关闭"><X size={15} /></button></div>}

        {view === 'friends' ? <FriendsPanel /> : !activeProject ? (
          <div className="empty-workspace">
            <span className="large-count">01</span>
            <FilePlus2 size={38} />
            <h1>创建第一份 LaTeX 项目</h1>
            <p>创建项目后开始编辑与编译。</p>
            <button className="compile-button" onClick={() => setShowCreate(true)}>新建项目</button>
          </div>
        ) : projectSurface === 'modeling' ? (
          <ModelingDashboard
            project={activeProject}
            onOpenEditor={() => setProjectSurface('editor')}
            onCopyCommand={copyModelingCommand}
          />
        ) : (
          <div className="editing-area">
            <div className="split-workspace" ref={splitHost}>
              <section className="editor-pane" style={{ width: `${split}%` }}>
                <div className="pane-label"><span>源文件</span><strong>main.tex</strong></div>
                <CollaborativeEditor projectId={activeProject.id} user={user} onStatus={setSync} onSourceChange={setSource} onCollaborators={setCollaborators} />
              </section>
              <button
                className="split-handle"
                role="separator"
                aria-label="调整编辑器和 PDF 宽度"
                aria-orientation="vertical"
                aria-valuemin={30}
                aria-valuemax={75}
                aria-valuenow={Math.round(split)}
                aria-valuetext={`编辑器占 ${Math.round(split)}%`}
                onPointerDown={beginResize}
                onKeyDown={resizeWithKeyboard}
              ><span /></button>
              <section className="preview-pane" style={{ width: `${100 - split}%` }}>
                <div className="pane-label"><span>输出</span><strong>PDF 预览</strong></div>
                {pdfUrl ? <iframe src={pdfUrl} title="编译后的 PDF" /> : compile && !compile.ok ? (
                  <div className="compile-diagnostic"><CircleAlert size={34} /><h2>编译未完成</h2><pre>{compile.log}</pre></div>
                ) : (
                  <div className="preview-empty"><span className="page-outline"><span>Q</span></span><h2>等待编译</h2><p>点击“编译”生成 PDF。</p></div>
                )}
              </section>
            </div>
            {showAgent && <AgentPanel projectId={activeProject.id} source={source} onClose={() => setShowAgent(false)} />}
          </div>
        )}
      </main>

      {showCreate && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowCreate(false)}>
          <form className="modal" onSubmit={createProject} onMouseDown={(event) => event.stopPropagation()}>
            <header><div><p className="eyebrow">新项目</p><h2>创建 LaTeX 项目</h2></div><button type="button" className="icon-button" onClick={() => setShowCreate(false)} aria-label="关闭新建项目对话框"><X size={19} /></button></header>
            <label htmlFor="projectName">项目名称</label>
            <input id="projectName" autoFocus value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="例如：竞赛论文" maxLength={60} />
            <p>将创建 `main.tex`，之后可通过分享按钮邀请协作者。</p>
            <footer><button type="button" className="secondary-button" onClick={() => setShowCreate(false)}>取消</button><button className="compile-button" disabled={!projectName.trim()}>创建项目</button></footer>
          </form>
        </div>
      )}
    </div>
  )
}
