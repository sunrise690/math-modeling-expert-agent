import { afterEach, describe, expect, it } from 'vitest'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import type { Server } from 'node:http'
import { createApp } from './app.js'
import { ProjectFileStore } from './project-files.js'
import { Store } from './store.js'

const servers: Server[] = []
const directories: string[] = []

afterEach(async () => {
  for (const server of servers.splice(0)) await new Promise<void>((resolve) => server.close(() => resolve()))
  for (const directory of directories.splice(0)) await rm(directory, { recursive: true, force: true })
})

async function startTestServer() {
  const storeDirectory = await mkdtemp(join(tmpdir(), 'qilintex-online-store-'))
  const fileDirectory = await mkdtemp(join(tmpdir(), 'qilintex-online-files-'))
  directories.push(storeDirectory, fileDirectory)
  const { app } = await createApp(new Store(storeDirectory), new ProjectFileStore(fileDirectory))
  const server = app.listen(0, '127.0.0.1')
  servers.push(server)
  await new Promise<void>((resolve) => server.once('listening', resolve))
  const address = server.address()
  if (!address || typeof address === 'string') throw new Error('测试服务未取得端口。')
  return `http://127.0.0.1:${address.port}`
}

describe('在线界面能力边界', () => {
  it('声明在线端不提供桌面下载并且仍要求本机 Agent', async () => {
    const origin = await startTestServer()
    const response = await fetch(`${origin}/health`)
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      onlineSurface: { desktopDownloads: false, localAgentRequired: true }
    })
  })

  it('拒绝根路径及子路径下的客户端安装包请求', async () => {
    const origin = await startTestServer()
    for (const path of ['/downloads', '/downloads/Qilintex-Setup.exe']) {
      const response = await fetch(`${origin}${path}`)
      expect(response.status).toBe(404)
      await expect(response.json()).resolves.toEqual({ error: '在线工作台不提供客户端安装包。' })
    }
  })
})
