import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronRight, File, FileCode2, FilePlus2, Folder, FolderOpen, FolderPlus, Upload } from 'lucide-react'
import { api } from '../lib/api'
import type { ProjectFileEntry } from '../lib/types'

interface Props {
  projectId: string
  projectName: string
  selectedPath: string
  onSelect: (entry: ProjectFileEntry) => void
  onMessage: (message: string, tone: 'success' | 'error') => void
}

function parentPath(path: string) {
  const segments = path.split('/')
  segments.pop()
  return segments.join('/')
}

function joinPath(folder: string, name: string) {
  return folder ? `${folder}/${name}` : name
}

function sortEntries(entries: ProjectFileEntry[]) {
  return [...entries].sort((left, right) => {
    if (left.path === 'main.tex') return -1
    if (right.path === 'main.tex') return 1
    const leftParent = parentPath(left.path)
    const rightParent = parentPath(right.path)
    if (leftParent === rightParent && left.kind !== right.kind) return left.kind === 'folder' ? -1 : 1
    return left.path.localeCompare(right.path, 'zh-CN')
  })
}

export function ProjectFilesPanel({ projectId, projectName, selectedPath, onSelect, onMessage }: Props) {
  const [entries, setEntries] = useState<ProjectFileEntry[]>([])
  const [targetFolder, setTargetFolder] = useState('')
  const [creating, setCreating] = useState<'file' | 'folder' | null>(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  const uploadRef = useRef<HTMLInputElement>(null)

  const refresh = useCallback(async () => {
    const payload = await api.projectFiles(projectId)
    setEntries(sortEntries(payload.files))
  }, [projectId])

  useEffect(() => {
    setTargetFolder('')
    setCreating(null)
    setExpandedFolders(new Set())
    void refresh().catch((error) => onMessage(error instanceof Error ? error.message : '无法读取项目文件。', 'error'))
    const timer = window.setInterval(() => { void refresh().catch(() => undefined) }, 5000)
    return () => window.clearInterval(timer)
  }, [projectId, refresh])

  useEffect(() => {
    const parents = selectedPath.split('/').slice(0, -1)
    if (!parents.length) return
    setExpandedFolders((current) => {
      const next = new Set(current)
      parents.forEach((_segment, index) => next.add(parents.slice(0, index + 1).join('/')))
      return next
    })
  }, [selectedPath])

  const beginCreate = (kind: 'file' | 'folder') => {
    setCreating(kind)
    setName('')
  }

  const create = async () => {
    const trimmed = name.trim()
    if (!trimmed || /[\\/]/.test(trimmed)) {
      onMessage('名称不能为空，也不能包含斜杠。', 'error')
      return
    }
    setBusy(true)
    try {
      const path = joinPath(targetFolder, trimmed)
      if (creating === 'folder') {
        await api.createProjectFolder(projectId, path)
        setTargetFolder(path)
        setExpandedFolders((current) => new Set(current).add(path))
        onMessage(`已新建文件夹 ${path}`, 'success')
      } else {
        const { file } = await api.uploadProjectFile(projectId, path, new Blob([''], { type: 'text/plain' }))
        if (file) onSelect(file)
        onMessage(`已新建文件 ${path}`, 'success')
      }
      setCreating(null)
      setName('')
      await refresh()
    } catch (error) {
      onMessage(error instanceof Error ? error.message : '新建失败。', 'error')
    } finally {
      setBusy(false)
    }
  }

  const toggleFolder = (path: string) => {
    setTargetFolder(path)
    setExpandedFolders((current) => {
      const next = new Set(current)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  const visibleEntries = entries.filter((entry) => {
    const segments = entry.path.split('/').slice(0, -1)
    return segments.every((_segment, index) => expandedFolders.has(segments.slice(0, index + 1).join('/')))
  })

  const upload = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    try {
      let last: ProjectFileEntry | undefined
      for (const file of Array.from(files)) {
        const result = await api.uploadProjectFile(projectId, joinPath(targetFolder, file.name), file)
        last = result.file
      }
      await refresh()
      if (last) onSelect(last)
      onMessage(`已将 ${files.length} 个文件放入 /${targetFolder}`, 'success')
    } catch (error) {
      onMessage(error instanceof Error ? error.message : '上传失败。', 'error')
    } finally {
      setBusy(false)
      if (uploadRef.current) uploadRef.current.value = ''
    }
  }

  return (
    <aside className="project-files-panel" aria-label="项目文件">
      <header><strong>{projectName}</strong><span>{entries.filter((entry) => entry.kind === 'file').length}</span></header>
      <div className="file-toolbar">
        <button type="button" onClick={() => beginCreate('file')} disabled={busy} title="新建文件" aria-label="新建文件"><FilePlus2 size={15} /></button>
        <button type="button" onClick={() => beginCreate('folder')} disabled={busy} title="新建文件夹" aria-label="新建文件夹"><FolderPlus size={15} /></button>
        <button type="button" onClick={() => uploadRef.current?.click()} disabled={busy} title="上传到当前放入位置" aria-label="上传文件"><Upload size={15} /></button>
        <input ref={uploadRef} type="file" multiple hidden onChange={(event) => { void upload(event.target.files) }} />
      </div>
      <button className="file-destination" type="button" onClick={() => setTargetFolder('')} title="点击返回项目根目录">
        <span>放入位置</span><strong>/{targetFolder}</strong>
      </button>
      {targetFolder && <button className="file-parent" type="button" onClick={() => setTargetFolder(parentPath(targetFolder))}><ChevronRight size={13} />返回上一级</button>}
      {creating && (
        <div className="file-create-row">
          {creating === 'folder' ? <FolderPlus size={14} /> : <FilePlus2 size={14} />}
          <input autoFocus value={name} disabled={busy} placeholder={creating === 'folder' ? '文件夹名称' : '文件名.tex'} onChange={(event) => setName(event.target.value)} onKeyDown={(event) => {
            if (event.key === 'Enter') void create()
            if (event.key === 'Escape') setCreating(null)
          }} onBlur={() => { if (!busy && !name.trim()) setCreating(null) }} />
        </div>
      )}
      <div className="file-tree">
        {visibleEntries.map((entry) => {
          const depth = entry.path.split('/').length - 1
          const label = entry.path.split('/').at(-1)
          const selected = entry.path === selectedPath
          const destination = entry.kind === 'folder' && entry.path === targetFolder
          return (
            <button
              type="button"
              key={`${entry.kind}:${entry.path}`}
              className={`${selected ? 'selected ' : ''}${destination ? 'destination' : ''}`.trim()}
              style={{ paddingLeft: `${9 + depth * 13}px` }}
              onClick={() => entry.kind === 'folder' ? toggleFolder(entry.path) : onSelect(entry)}
              title={entry.kind === 'folder' ? `${expandedFolders.has(entry.path) ? '折叠' : '展开'} /${entry.path}，并设为新文件位置` : entry.path}
            >
              {entry.kind === 'folder'
                ? <><ChevronRight className={expandedFolders.has(entry.path) ? 'file-twisty open' : 'file-twisty'} size={12} />{expandedFolders.has(entry.path) ? <FolderOpen size={15} /> : <Folder size={15} />}</>
                : <><span className="file-twisty-spacer" />{entry.editable ? <FileCode2 size={15} /> : <File size={15} />}</>}
              <span>{label}</span>
            </button>
          )
        })}
      </div>
      <footer>单文件 8 MB · 项目 100 MB</footer>
    </aside>
  )
}
