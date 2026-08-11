import { Server } from '@hocuspocus/server'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import * as Y from 'yjs'
import { config } from './config.js'
import { verifySessionDetails } from './auth.js'
import { Store } from './store.js'

function projectIdFromDocument(name: string) {
  const match = /^project\.([0-9a-f-]{36})\.main\.tex$/i.exec(name)
  if (!match) throw new Error('文档名称无效。')
  return match[1]
}

export async function startCollaboration(store: Store) {
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
      if (!store.canAccessProject(projectIdFromDocument(documentName), session.userId)) throw new Error('没有项目访问权限。')
      return { userId: session.userId, authRealm: session.realm }
    },
    async onLoadDocument({ documentName, document }) {
      const projectId = projectIdFromDocument(documentName)
      const file = join(directory, `${projectId}.bin`)
      try {
        Y.applyUpdate(document, new Uint8Array(await readFile(file)))
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error
        const source = store.projectById(projectId)?.mainTex || ''
        if (source) document.getText('content').insert(0, source)
      }
      return document
    },
    async onStoreDocument({ documentName, document }) {
      const projectId = projectIdFromDocument(documentName)
      await writeFile(join(directory, `${projectId}.bin`), Y.encodeStateAsUpdate(document))
    }
  })

  await server.listen()
  return server
}
