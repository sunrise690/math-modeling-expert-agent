import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BookOpenText, Bot, Check, ChevronRight, CircleAlert, FileCode2, FilePlus2, Files,
  LayoutDashboard, LogOut, Menu, PanelLeftClose, PanelLeftOpen, Play, Share2,
  Search, Settings, Users, X
} from 'lucide-react'
import { api, setToken } from '../lib/api'
import type { AgentMode, AgentResult, CompileResult, Project, ProjectFileEntry, User } from '../lib/types'
import { AgentPanel } from './AgentPanel'
import { CollaborativeEditor } from './CollaborativeEditor'
import { Avatar, FriendsPanel } from './FriendsPanel'
import { ModelingDashboard } from './ModelingDashboard'
import { ProjectFilesPanel } from './ProjectFilesPanel'
import { UpdateButton } from './UpdateButton'
import { ApiSettings } from './ApiSettings'
import { ProfilePanel } from './ProfilePanel'
import { invitationFromSearch } from '../lib/urls'

interface Props {
  user: User
  onUserChanged: (user: User) => void
  onLogout: () => void
}

type SyncState = 'connecting' | 'connected' | 'disconnected'
type Notice = { message: string; tone: 'success' | 'error' }
type CommandAction = { id: string; label: string; detail: string; shortcut?: string; run: () => void | Promise<void> }

export function Workbench({ user, onUserChanged, onLogout }: Props) {
  const [projects, setProjects] = useState<Project[]>([])
  const [activeId, setActiveId] = useState('')
  const [view, setView] = useState<'projects' | 'friends'>('projects')
  const [showCreate, setShowCreate] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [showCommandPalette, setShowCommandPalette] = useState(false)
  const [commandQuery, setCommandQuery] = useState('')
  const [projectName, setProjectName] = useState('')
  const [selectedFile, setSelectedFile] = useState<ProjectFileEntry>({ path: 'main.tex', kind: 'file', size: 0, editable: true })
  const [source, setSource] = useState('')
  const [sync, setSync] = useState<SyncState>('connecting')
  const [collaborators, setCollaborators] = useState<User[]>([])
  const [compile, setCompile] = useState<CompileResult | null>(null)
  const [compiling, setCompiling] = useState(false)
  const [showAgent, setShowAgent] = useState(false)
  const [agentPrompt, setAgentPrompt] = useState('')
  const [agentMode, setAgentMode] = useState<AgentMode>('auto')
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
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'p') {
        event.preventDefault()
        setCommandQuery('')
        setShowCommandPalette(true)
      } else if (event.key === 'Escape') {
        setShowCommandPalette(false)
      }
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  useEffect(() => {
    if (activeId) localStorage.setItem('tonggao.activeProject', activeId)
    setCompile(null)
    setSource('')
    setSelectedFile({ path: 'main.tex', kind: 'file', size: 0, editable: true })
    setCollaborators([])
    setShowAgent(false)
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

  const runModelingStage = async (command: string, _label: string): Promise<AgentResult> => {
    if (!activeProject) throw new Error('请先选择项目。')
    const mode: AgentMode = command === 'end-to-end' ? 'cumcm' : command === 'write' ? 'paper' : ['audit', 'polish', 'status'].includes(command) ? 'reviewer' : 'solver'
    return api.askAgent(activeProject.id, source, `$cumcm-modeling ${command} 当前项目“${activeProject.name}”`, mode)
  }

  const logout = async () => {
    await api.logout().catch(() => undefined)
    setToken()
    onLogout()
  }

  const commandActions: CommandAction[] = [
    { id: 'new-project', label: '新建项目', detail: '创建共享的建模与 QilinTeX 项目', run: () => setShowCreate(true) },
    { id: 'friends', label: '打开好友与协作', detail: '搜索成员并处理好友申请', run: () => setView('friends') },
    { id: 'api-settings', label: '配置模型与 API', detail: '选择模型通道、API 地址与密钥', run: () => setShowSettings(true) },
    ...(activeProject ? [
      { id: 'modeling', label: '切换到建模 Agent', detail: activeProject.name, run: () => { setView('projects'); setProjectSurface('modeling') } },
      { id: 'editor', label: '打开 QilinTeX', detail: `${activeProject.name} · ${selectedFile.path}`, run: () => { setView('projects'); setProjectSurface('editor') } },
      { id: 'agent', label: '打开数模 Agent 面板', detail: '在当前项目上下文中提问', run: () => { setView('projects'); setAgentPrompt(''); setAgentMode('auto'); setShowAgent(true) } },
      { id: 'share', label: '复制项目邀请链接', detail: '邀请成员加入当前项目', run: share },
      ...(projectSurface === 'editor' ? [{ id: 'compile', label: '编译当前论文', detail: '生成 main.tex 的 PDF 预览', run: runCompile }] : [])
    ] satisfies CommandAction[] : [])
  ]
  const normalizedCommandQuery = commandQuery.trim().toLocaleLowerCase()
  const filteredCommands = commandActions
    .map((action, index) => {
      const label = action.label.toLocaleLowerCase()
      const detail = action.detail.toLocaleLowerCase()
      const score = !normalizedCommandQuery ? 0
        : label.startsWith(normalizedCommandQuery) ? 0
          : label.includes(normalizedCommandQuery) ? 1
            : detail.includes(normalizedCommandQuery) ? 2
              : Number.POSITIVE_INFINITY
      return { action, index, score }
    })
    .filter((entry) => Number.isFinite(entry.score))
    .sort((left, right) => left.score - right.score || left.index - right.index)
    .map((entry) => entry.action)
  const runCommand = (action: CommandAction) => {
    setShowCommandPalette(false)
    setCommandQuery('')
    void action.run()
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
      <nav className="activity-bar" aria-label="工作台活动栏">
        <div className="activity-brand" title="数模工作台"><img src="./app-icon.jpg" alt="" /></div>
        <button className={view === 'projects' ? 'active' : ''} onClick={() => setView('projects')} aria-label="项目资源管理器" title="项目资源管理器"><Files size={23} /></button>
        <button className={view === 'friends' ? 'active' : ''} onClick={() => setView('friends')} aria-label="好友与协作" title="好友与协作"><Users size={23} /></button>
        <button
          className={showAgent && view === 'projects' ? 'active' : ''}
          disabled={!activeProject}
          onClick={() => { setView('projects'); setAgentPrompt(''); setAgentMode('auto'); setShowAgent((current) => !current) }}
          aria-label="数模 Agent"
          title="数模 Agent"
        ><Bot size={23} /></button>
        <span className="activity-spacer" />
        <button onClick={() => setShowSettings(true)} aria-label="模型与 API 设置" title="模型与 API 设置"><Settings size={22} /></button>
        <button className="activity-account" title={`${user.displayName} · @${user.handle} · 查看个人资料`} onClick={() => setShowProfile(true)} aria-label="查看个人资料"><Avatar user={user} small /></button>
      </nav>

      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="sidebar-heading">
            <strong>{view === 'projects' ? '资源管理器' : '好友与协作'}</strong>
            <span>{view === 'projects' ? '数模工作区' : '团队工作区'}</span>
          </div>
          <button className="icon-button sidebar-close" onClick={() => setSidebarOpen(false)} aria-label="收起侧栏"><PanelLeftClose size={19} /></button>
        </div>
        {view === 'projects' ? <>
          <div className="project-list-head"><span>我的项目</span><span className="nav-count">{projects.length}</span><button onClick={() => setShowCreate(true)} aria-label="新建项目"><FilePlus2 size={17} /></button></div>
          <div className={`project-list${activeProject ? ' has-files' : ''}`}>
            {projects.map((project) => (
              <button key={project.id} className={activeId === project.id ? 'active' : ''} onClick={() => setActiveId(project.id)}>
                <ChevronRight className={activeId === project.id ? 'project-chevron open' : 'project-chevron'} size={13} /><FileCode2 size={16} /><span>{project.name}</span>
              </button>
            ))}
            {projects.length === 0 && <p className="sidebar-empty">尚未创建项目</p>}
          </div>
          {activeProject && <ProjectFilesPanel
            projectId={activeProject.id}
            projectName={activeProject.name}
            selectedPath={selectedFile.path}
            onSelect={(entry) => { setSelectedFile(entry); setProjectSurface('editor') }}
            onMessage={(message, tone) => {
              setNotice({ message, tone })
              window.setTimeout(() => setNotice(null), 3000)
            }}
          />}
        </> : <div className="sidebar-context">
          <Users size={18} />
          <strong>团队成员</strong>
          <p>在主编辑区搜索好友、处理申请并管理协作关系。</p>
        </div>}

        <div className="user-menu">
          <button className="user-avatar-button" onClick={() => setShowProfile(true)} title="查看个人资料"><Avatar user={user} small /></button>
          <div><strong>{user.displayName}</strong><span>@{user.handle}</span></div>
          <button className="icon-button" onClick={logout} aria-label="退出登录"><LogOut size={17} /></button>
        </div>
      </aside>

      <main className="workspace">
        <header className="workspace-bar">
          <div className="project-title">
            {!sidebarOpen && <button className="icon-button" onClick={() => setSidebarOpen(true)} aria-label="展开侧栏"><PanelLeftOpen size={19} /></button>}
            <span className="project-index">{activeProject ? String(projects.findIndex((item) => item.id === activeProject.id) + 1).padStart(2, '0') : '—'}</span>
            <div><strong>{view === 'friends' ? '好友' : activeProject?.name || '项目'}</strong><span>{view === 'friends' ? '联系人' : activeProject ? projectSurface === 'modeling' ? '建模 Agent' : `QilinTeX · ${selectedFile.path}` : '未选择项目'}</span></div>
          </div>
          <button className="command-center" onClick={() => { setCommandQuery(''); setShowCommandPalette(true) }} aria-label="打开快速命令">
            <Search size={13} />
            <span>{activeProject ? activeProject.name : '快速命令'}</span>
            <kbd>Ctrl P</kbd>
          </button>
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
              <UpdateButton />
              <button className="toolbar-button" onClick={share}><Share2 size={16} />分享</button>
              <button className="toolbar-button" onClick={() => { setAgentPrompt(''); setAgentMode('auto'); setShowAgent((current) => !current) }}><Bot size={16} />Agent</button>
              {projectSurface === 'editor' && <button className="compile-button" onClick={runCompile} disabled={compiling}><Play size={16} />{compiling ? '编译中' : '编译'}</button>}
            </div>
          )}
          <button className="mobile-menu icon-button" onClick={() => setSidebarOpen((value) => !value)} aria-label="菜单"><Menu size={20} /></button>
        </header>

        {view === 'projects' && activeProject && (
          <nav className="workspace-tabs" aria-label="项目工作区">
            <button aria-pressed={projectSurface === 'modeling'} className={projectSurface === 'modeling' ? 'active' : ''} onClick={() => setProjectSurface('modeling')}><LayoutDashboard size={15} /><span>建模 Agent</span><small>流程</small></button>
            <button aria-pressed={projectSurface === 'editor'} className={projectSurface === 'editor' ? 'active' : ''} onClick={() => setProjectSurface('editor')}><BookOpenText size={15} /><span>QilinTeX</span><small>{selectedFile.path}</small></button>
          </nav>
        )}

        {notice && <div className={`notice ${notice.tone}`} role="status" aria-live="polite">{notice.tone === 'success' ? <Check size={16} /> : <CircleAlert size={16} />}{notice.message}<button onClick={() => setNotice(null)} aria-label="关闭"><X size={15} /></button></div>}

        {view === 'friends' ? <FriendsPanel currentUser={user} /> : !activeProject ? (
          <div className="empty-workspace">
            <span className="large-count">01</span>
            <FilePlus2 size={38} />
            <h1>创建第一个数模项目</h1>
            <p>建模任务、结果工件与论文将在同一项目中协作。</p>
            <button className="compile-button" onClick={() => setShowCreate(true)}>新建项目</button>
          </div>
        ) : (
          <div className="project-workspace">
            {projectSurface === 'modeling' ? (
              <ModelingDashboard
                project={activeProject}
                onOpenEditor={() => setProjectSurface('editor')}
                onRunAgent={runModelingStage}
              />
            ) : (
              <div className="editing-area">
                <div className="split-workspace" ref={splitHost}>
                  <section className="editor-pane" style={{ width: `${split}%` }}>
                    <div className="editor-body">
                      <div className="editor-document">
                        <div className="pane-label"><span>源文件</span><strong>{selectedFile.path}</strong></div>
                        {selectedFile.editable ? (
                          <CollaborativeEditor
                            projectId={activeProject.id}
                            filePath={selectedFile.path}
                            user={user}
                            onStatus={setSync}
                            onSourceChange={(value) => { if (selectedFile.path === 'main.tex') setSource(value) }}
                            onCollaborators={setCollaborators}
                          />
                        ) : (
                          <div className="file-resource-placeholder">
                            <FileCode2 size={30} />
                            <h2>{selectedFile.path}</h2>
                            <p>该资源会随项目保存并参与编译，但不支持在文本编辑器中打开。</p>
                          </div>
                        )}
                      </div>
                    </div>
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
              </div>
            )}
            {showAgent && (
              <AgentPanel
                projectId={activeProject.id}
                source={source}
                surface={projectSurface === 'editor' ? 'paper' : 'modeling'}
                initialMessage={agentPrompt}
                initialMode={agentMode}
                onOpenSettings={() => { setShowSettings(true); setShowAgent(false) }}
                onClose={() => setShowAgent(false)}
              />
            )}
          </div>
        )}

        <footer className="status-bar" aria-label="工作台状态">
          <div><Check size={12} /><span>{projectSurface === 'editor' ? sync === 'connected' ? '已同步' : sync === 'connecting' ? '正在连接' : '离线' : '建模工作区已就绪'}</span></div>
          <div className="status-spacer" />
          {activeProject && <span>{activeProject.name}</span>}
          <span>{projectSurface === 'editor' ? 'LaTeX' : '数模流程'}</span>
          <span>UTF-8</span>
          <span>Agent + QilinTeX</span>
        </footer>
      </main>

      {showCreate && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowCreate(false)}>
          <form className="modal" onSubmit={createProject} onMouseDown={(event) => event.stopPropagation()}>
            <header><div><p className="eyebrow">新项目</p><h2>创建数模项目</h2></div><button type="button" className="icon-button" onClick={() => setShowCreate(false)} aria-label="关闭新建项目对话框"><X size={19} /></button></header>
            <label htmlFor="projectName">项目名称</label>
            <input id="projectName" autoFocus value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="例如：2026 国赛 A 题" maxLength={60} />
            <p>将同时建立建模工作区与 QilinTeX `main.tex`，并共享项目上下文。</p>
            <footer><button type="button" className="secondary-button" onClick={() => setShowCreate(false)}>取消</button><button className="compile-button" disabled={!projectName.trim()}>创建项目</button></footer>
          </form>
        </div>
      )}

      {showSettings && <ApiSettings onClose={() => setShowSettings(false)} onSaved={(message) => {
        setNotice({ message, tone: 'success' })
        window.setTimeout(() => setNotice(null), 3000)
      }} />}

      {showProfile && <ProfilePanel user={user} onClose={() => setShowProfile(false)} onUpdated={(next) => {
        onUserChanged(next)
        setNotice({ message: '个人资料已更新。', tone: 'success' })
        window.setTimeout(() => setNotice(null), 3000)
      }} />}

      {showCommandPalette && (
        <div className="command-backdrop" role="presentation" onMouseDown={() => setShowCommandPalette(false)}>
          <section className="command-palette" role="dialog" aria-modal="true" aria-label="快速命令" onMouseDown={(event) => event.stopPropagation()}>
            <header>
              <Search size={17} />
              <input
                autoFocus
                value={commandQuery}
                onChange={(event) => setCommandQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && filteredCommands[0]) runCommand(filteredCommands[0])
                }}
                placeholder="输入项目操作"
                aria-label="搜索命令"
              />
            </header>
            <div className="command-results">
              {filteredCommands.map((action, index) => (
                <button key={action.id} className={index === 0 ? 'selected' : ''} onClick={() => runCommand(action)}>
                  <span><strong>{action.label}</strong><small>{action.detail}</small></span>
                  {action.shortcut && <kbd>{action.shortcut}</kbd>}
                </button>
              ))}
              {filteredCommands.length === 0 && <p>没有匹配的命令</p>}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
