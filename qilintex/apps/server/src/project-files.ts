import { copyFile, mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises'
import { extname, join, relative, resolve, sep } from 'node:path'
import { config } from './config.js'

export interface ProjectFileEntry {
  path: string
  kind: 'file' | 'folder'
  size: number
  editable: boolean
}

const EDITABLE_EXTENSIONS = new Set(['.tex', '.bib', '.bst', '.cls', '.sty', '.md', '.txt', '.csv', '.json', '.yaml', '.yml'])
const MAX_FILE_BYTES = 8 * 1024 * 1024
const MAX_TEXT_BYTES = 1024 * 1024
const MAX_PROJECT_BYTES = 100 * 1024 * 1024

export function normalizeProjectPath(value: string, allowRoot = false) {
  const normalized = String(value || '').normalize('NFKC').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
  if (!normalized) {
    if (allowRoot) return ''
    throw new Error('请填写文件或文件夹路径。')
  }
  if (normalized.length > 240) throw new Error('项目路径不能超过 240 个字符。')
  const segments = normalized.split('/')
  if (segments.some((segment) => !segment || segment === '.' || segment === '..' || segment.length > 80
    || /[<>:"|?*\u0000-\u001f]/.test(segment) || /[. ]$/.test(segment))) {
    throw new Error('项目路径包含无效名称。')
  }
  return segments.join('/')
}

function editable(path: string, size: number) {
  return size <= MAX_TEXT_BYTES && EDITABLE_EXTENSIONS.has(extname(path).toLowerCase())
}

export class ProjectFileStore {
  private root: string

  constructor(dataDir = config.dataDir) {
    this.root = join(dataDir, 'project-files')
  }

  private projectRoot(projectId: string) {
    if (!/^[0-9a-f-]{36}$/i.test(projectId)) throw new Error('项目标识无效。')
    return join(this.root, projectId)
  }

  private target(projectId: string, path: string, allowRoot = false) {
    const root = resolve(this.projectRoot(projectId))
    const normalized = normalizeProjectPath(path, allowRoot)
    const target = resolve(root, normalized)
    if (target !== root && !target.startsWith(`${root}${sep}`)) throw new Error('项目路径越界。')
    return { root, target, path: normalized }
  }

  async list(projectId: string): Promise<ProjectFileEntry[]> {
    const root = this.projectRoot(projectId)
    await mkdir(root, { recursive: true })
    const entries: ProjectFileEntry[] = [{ path: 'main.tex', kind: 'file', size: 0, editable: true }]

    const visit = async (directory: string) => {
      const children = await readdir(directory, { withFileTypes: true })
      for (const child of children) {
        if (child.isSymbolicLink()) continue
        const absolute = join(directory, child.name)
        const path = relative(root, absolute).split(sep).join('/')
        if (path === 'main.tex') continue
        if (child.isDirectory()) {
          entries.push({ path, kind: 'folder', size: 0, editable: false })
          await visit(absolute)
        } else if (child.isFile()) {
          const details = await stat(absolute)
          entries.push({ path, kind: 'file', size: details.size, editable: editable(path, details.size) })
        }
      }
    }

    await visit(root)
    return entries.sort((left, right) => left.path.localeCompare(right.path, 'zh-CN'))
  }

  async createFolder(projectId: string, path: string) {
    const target = this.target(projectId, path)
    await mkdir(target.target, { recursive: true })
    return target.path
  }

  async writeFile(projectId: string, path: string, content: Buffer) {
    const target = this.target(projectId, path)
    if (target.path === 'main.tex') throw new Error('main.tex 由协作编辑器管理，不能通过上传覆盖。')
    if (content.byteLength > MAX_FILE_BYTES) throw new Error('单个文件不能超过 8 MB。')
    const currentSize = (await this.list(projectId)).reduce((sum, item) => sum + item.size, 0)
    let replacedSize = 0
    try { replacedSize = (await stat(target.target)).size } catch { /* new file */ }
    if (currentSize - replacedSize + content.byteLength > MAX_PROJECT_BYTES) throw new Error('项目文件总大小不能超过 100 MB。')
    await mkdir(resolve(target.target, '..'), { recursive: true })
    await writeFile(target.target, content)
    return target.path
  }

  async readText(projectId: string, path: string) {
    const target = this.target(projectId, path)
    const details = await stat(target.target)
    if (!details.isFile() || !editable(target.path, details.size)) throw new Error('该文件不支持文本编辑。')
    return readFile(target.target, 'utf8')
  }

  async writeText(projectId: string, path: string, content: string) {
    const data = Buffer.from(content, 'utf8')
    if (data.byteLength > MAX_TEXT_BYTES) throw new Error('文本文件不能超过 1 MB。')
    return this.writeFile(projectId, path, data)
  }

  async copyInto(projectId: string, destination: string) {
    const root = this.projectRoot(projectId)
    for (const entry of await this.list(projectId)) {
      if (entry.path === 'main.tex') continue
      const output = join(destination, ...entry.path.split('/'))
      if (entry.kind === 'folder') await mkdir(output, { recursive: true })
      else {
        await mkdir(resolve(output, '..'), { recursive: true })
        await copyFile(join(root, ...entry.path.split('/')), output)
      }
    }
  }
}
