import { raw, Router } from 'express'
import { compileLatex } from './compiler.js'
import { config } from './config.js'
import { requireUser } from './auth.js'
import { Store, toPublicUser } from './store.js'
import { ProjectFileStore } from './project-files.js'

export function apiRouter(store: Store, projectFiles: ProjectFileStore) {
  const router = Router()
  router.use(requireUser)

  const localAgentOnly = (_request: unknown, response: { status: (code: number) => { json: (payload: object) => void } }) => {
    response.status(410).json({ error: '模型登录、API 配置与 Agent 运行只允许通过当前用户的本机运行器完成。' })
  }

  router.get('/agent-config', localAgentOnly)
  router.post('/agent-config/test', localAgentOnly)
  router.post('/agent-config', localAgentOnly)
  router.post('/agent-config/codex-login', localAgentOnly)
  router.get('/agent-config/codex-login/:sessionId', localAgentOnly)
  router.post('/agent-config/codex-login/:sessionId/callback', localAgentOnly)
  router.delete('/agent-config/codex-login/:sessionId', localAgentOnly)

  router.get('/profile', (request, response) => {
    response.json({ user: toPublicUser(request.user!, true) })
  })

  router.patch('/profile', async (request, response) => {
    const displayName = String(request.body?.displayName || '').normalize('NFKC').trim().slice(0, 32)
    const rawEmail = String(request.body?.email || '').normalize('NFKC').trim().toLocaleLowerCase()
    const avatarUrl = String(request.body?.avatarUrl || '').trim()
    if (!displayName) return response.status(400).json({ error: '昵称不能为空。' })
    if (rawEmail && (rawEmail.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(rawEmail))) return response.status(400).json({ error: '邮箱格式无效。' })
    const remoteAvatar = /^https:\/\/[^\s]+$/i.test(avatarUrl) && avatarUrl.length <= 2_000
    const inlineAvatar = /^data:image\/(?:png|jpeg|webp);base64,[a-z0-9+/=]+$/i.test(avatarUrl) && avatarUrl.length <= 700_000
    if (avatarUrl && !remoteAvatar && !inlineAvatar) return response.status(400).json({ error: '头像需为 HTTPS 图片地址，或小于 500 KB 的 PNG/JPEG/WebP 图片。' })
    try {
      const user = await store.updateUserProfile(request.user!.id, {
        displayName,
        email: rawEmail || undefined,
        avatarUrl: avatarUrl || undefined
      })
      response.json({ user: toPublicUser(user, true) })
    } catch (error) { response.status(409).json({ error: (error as Error).message }) }
  })

  router.get('/projects', (request, response) => response.json({ projects: store.listProjects(request.user!.id) }))

  router.post('/projects', async (request, response) => {
    const name = String(request.body?.name || '').trim().slice(0, 60)
    if (!name) return response.status(400).json({ error: '项目名称不能为空。' })
    response.status(201).json({ project: await store.createProject(request.user!.id, name) })
  })

  router.get('/projects/:projectId/files', async (request, response) => {
    if (!store.canAccessProject(request.params.projectId, request.user!.id)) return response.status(403).json({ error: '没有项目访问权限。' })
    response.json({ files: await projectFiles.list(request.params.projectId) })
  })

  router.post('/projects/:projectId/folders', async (request, response) => {
    if (!store.canAccessProject(request.params.projectId, request.user!.id)) return response.status(403).json({ error: '没有项目访问权限。' })
    try {
      response.status(201).json({ path: await projectFiles.createFolder(request.params.projectId, String(request.body?.path || '')) })
    } catch (error) { response.status(400).json({ error: (error as Error).message }) }
  })

  router.put('/projects/:projectId/files', raw({ type: '*/*', limit: '8mb' }), async (request, response) => {
    if (!store.canAccessProject(request.params.projectId, request.user!.id)) return response.status(403).json({ error: '没有项目访问权限。' })
    try {
      const path = await projectFiles.writeFile(request.params.projectId, String(request.query.path || ''), Buffer.isBuffer(request.body) ? request.body : Buffer.alloc(0))
      const file = (await projectFiles.list(request.params.projectId)).find((item) => item.path === path)
      response.status(201).json({ file })
    } catch (error) { response.status(400).json({ error: (error as Error).message }) }
  })

  router.post('/projects/:projectId/agent-uploads', raw({ type: '*/*', limit: '25mb' }), async (request, response) => {
    if (!store.canAccessProject(request.params.projectId, request.user!.id)) return response.status(403).json({ error: '没有项目访问权限。' })
    return response.status(410).json({ error: 'Agent 附件只提交到当前用户的本机运行器。' })
  })

  router.delete('/projects/:projectId/agent-uploads/:uploadId', async (request, response) => {
    if (!store.canAccessProject(request.params.projectId, request.user!.id)) return response.status(403).json({ error: '没有项目访问权限。' })
    return response.status(410).json({ error: 'Agent 附件只保存在当前用户的本机运行器。' })
  })

  router.post('/projects/:projectId/invitations', async (request, response) => {
    try {
      const invitation = await store.createInvitation(request.params.projectId, request.user!.id)
      response.json({ token: invitation.token, url: `${config.clientUrl}/?invite=${encodeURIComponent(invitation.token)}` , expiresAt: invitation.expiresAt })
    } catch (error) { response.status(403).json({ error: (error as Error).message }) }
  })

  router.post('/invitations/:token/accept', async (request, response) => {
    try { response.json({ project: await store.acceptInvitation(request.params.token, request.user!.id) }) }
    catch (error) { response.status(400).json({ error: (error as Error).message }) }
  })

  router.post('/projects/:projectId/compile', async (request, response) => {
    if (!store.canAccessProject(request.params.projectId, request.user!.id)) return response.status(403).json({ error: '没有项目访问权限。' })
    response.json(await compileLatex(String(request.body?.source || ''), (directory) => projectFiles.copyInto(request.params.projectId, directory)))
  })

  router.post('/projects/:projectId/agent', async (request, response) => {
    if (!store.canAccessProject(request.params.projectId, request.user!.id)) return response.status(403).json({ error: '没有项目访问权限。' })
    return response.status(410).json({ error: 'Agent 只在当前用户电脑上运行，服务器不再代用共享账号或共享 API。' })
  })

  router.get('/users/search', (request, response) => {
    const query = String(request.query.q || '').trim().slice(0, 60)
    response.json({ users: query ? store.searchUsers(request.user!.id, query).map((user) => toPublicUser(user)) : [] })
  })

  router.get('/friends', (request, response) => {
    const data = store.listFriends(request.user!.id)
    response.json({ friends: data.friends.map((user) => toPublicUser(user, true)), requests: data.requests.map((item) => ({ ...item, user: toPublicUser(item.user) })) })
  })

  router.post('/friends/requests', async (request, response) => {
    try { await store.requestFriend(request.user!.id, String(request.body?.userId || '')); response.status(201).json({ ok: true }) }
    catch (error) { response.status(400).json({ error: (error as Error).message }) }
  })

  router.post('/friends/requests/:requestId/accept', async (request, response) => {
    try { await store.acceptFriend(request.user!.id, request.params.requestId); response.json({ ok: true }) }
    catch (error) { response.status(400).json({ error: (error as Error).message }) }
  })

  router.get('/friends/:friendId/messages', (request, response) => {
    try { response.json({ messages: store.listDirectMessages(request.user!.id, request.params.friendId) }) }
    catch (error) { response.status(403).json({ error: (error as Error).message }) }
  })

  router.post('/friends/:friendId/messages', async (request, response) => {
    try { response.status(201).json({ message: await store.sendDirectMessage(request.user!.id, request.params.friendId, String(request.body?.body || '')) }) }
    catch (error) { response.status(400).json({ error: (error as Error).message }) }
  })

  return router
}
