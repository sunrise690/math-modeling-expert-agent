import { Server } from '@hocuspocus/server'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import * as Y from 'yjs'
import { config } from './config.js'
import { verifySessionDetails } from './auth.js'
import { Store } from './store.js'
import { normalizeProjectPath, ProjectFileStore } from './project-files.js'

function documentDetails(name: string) {
  const main = /^project\.([0-9a-f-]{36})\.main\.tex$/i.exec(name)
  if (main) return { projectId: main[1], path: 'main.tex' }
  const file = /^project\.([0-9a-f-]{36})\.file\.([A-Za-z0-9_-]+)$/i.exec(name)
  if (!file) throw new Error('文档名称无效。')
  try {
    return { projectId: file[1], path: normalizeProjectPath(Buffer.from(file[2], 'base64url').toString('utf8')) }
  } catch {
    throw new Error('文档路径无效。')
  }
}

export async function startCollaboration(store: Store, projectFiles: ProjectFileStore) {
  const directory = join(config.dataDir, 'collaboration')
  await mkdir(directory, { recursive: true })

  const server = new Server({
    address: config.host,
    port: config.collaborationPort,
    debounce: 1500,
    maxDebounce: 10_000,
    async onAuthenticate({ token, documentName }) {
      if (!token) throw new Error('需要登录。')
      const session = await verifySessionDetails(String(token))
      const user = store.userById(session.userId)
      if (!user || user.provider !== session.provider) throw new Error('登录用户不匹配。')
      if (!store.canAccessProject(documentDetails(documentName).projectId, session.userId)) throw new Error('没有项目访问权限。')
      return { userId: session.userId, authRealm: session.realm }
    },
    async onLoadDocument({ documentName, document }) {
      const details = documentDetails(documentName)
      if (details.path === 'main.tex') {
        try {
          Y.applyUpdate(document, new Uint8Array(await readFile(join(directory, `${details.projectId}.bin`))))
        } catch (error) {
          if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error
          const source = store.projectById(details.projectId)?.mainTex || ''
          if (source) document.getText('content').insert(0, source)
        }
      } else {
        try {
          const source = await projectFiles.readText(details.projectId, details.path)
          if (source) document.getText('content').insert(0, source)
        } catch (error) {
          if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error
        }
      }
      return document
    },
    async onStoreDocument({ documentName, document }) {
      const details = documentDetails(documentName)
      const source = document.getText('content').toString()
      if (details.path === 'main.tex') {
        await writeFile(join(directory, `${details.projectId}.bin`), Y.encodeStateAsUpdate(document))
        await store.updateMainTex(details.projectId, source)
      } else {
        await projectFiles.writeText(details.projectId, details.path, source)
      }
    }
  })

  await server.listen()
  return server
}
