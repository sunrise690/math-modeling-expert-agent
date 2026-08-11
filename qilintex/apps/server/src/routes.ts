import { Router } from 'express'
import { askDocumentAgent } from './agent.js'
import { compileLatex } from './compiler.js'
import { config } from './config.js'
import { requireUser } from './auth.js'
import { Store, toPublicUser } from './store.js'

export function apiRouter(store: Store) {
  const router = Router()
  router.use(requireUser)

  router.get('/projects', (request, response) => response.json({ projects: store.listProjects(request.user!.id) }))

  router.post('/projects', async (request, response) => {
    const name = String(request.body?.name || '').trim().slice(0, 60)
    if (!name) return response.status(400).json({ error: '项目名称不能为空。' })
    response.status(201).json({ project: await store.createProject(request.user!.id, name) })
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
    response.json(await compileLatex(String(request.body?.source || '')))
  })

  router.post('/projects/:projectId/agent', async (request, response) => {
    if (!store.canAccessProject(request.params.projectId, request.user!.id)) return response.status(403).json({ error: '没有项目访问权限。' })
    try {
      const result = await askDocumentAgent(String(request.body?.source || ''), String(request.body?.message || ''))
      response.json(result)
    } catch (error) { response.status(503).json({ error: (error as Error).message }) }
  })

  router.get('/users/search', (request, response) => {
    const query = String(request.query.q || '').trim().slice(0, 60)
    response.json({ users: query ? store.searchUsers(request.user!.id, query).map(toPublicUser) : [] })
  })

  router.get('/friends', (request, response) => {
    const data = store.listFriends(request.user!.id)
    response.json({ friends: data.friends.map(toPublicUser), requests: data.requests.map((item) => ({ ...item, user: toPublicUser(item.user) })) })
  })

  router.post('/friends/requests', async (request, response) => {
    try { await store.requestFriend(request.user!.id, String(request.body?.userId || '')); response.status(201).json({ ok: true }) }
    catch (error) { response.status(400).json({ error: (error as Error).message }) }
  })

  router.post('/friends/requests/:requestId/accept', async (request, response) => {
    try { await store.acceptFriend(request.user!.id, request.params.requestId); response.json({ ok: true }) }
    catch (error) { response.status(400).json({ error: (error as Error).message }) }
  })

  return router
}
