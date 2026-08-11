import { mkdir, readFile, rename, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { randomBytes, randomUUID } from 'node:crypto'
import { config } from './config.js'

export type Provider = 'team' | 'qq' | 'wechat' | 'dev'
export type Role = 'owner' | 'editor' | 'viewer'

export interface StoredUser {
  id: string
  provider: Provider
  providerId: string
  handle: string
  displayName: string
  avatarUrl?: string
  createdAt: string
}

export interface StoredProject {
  id: string
  name: string
  ownerId: string
  members: Array<{ userId: string; role: Role }>
  mainTex: string
  createdAt: string
  updatedAt: string
}

export function toPublicUser(user: StoredUser) {
  return { id: user.id, provider: user.provider, handle: user.handle, displayName: user.displayName, avatarUrl: user.avatarUrl }
}

interface FriendRequest { id: string; fromId: string; toId: string; status: 'pending' | 'accepted'; createdAt: string }
interface Friendship { id: string; leftId: string; rightId: string; createdAt: string }
interface Invitation { token: string; projectId: string; createdBy: string; expiresAt: string }
interface Database { users: StoredUser[]; projects: StoredProject[]; friendRequests: FriendRequest[]; friendships: Friendship[]; invitations: Invitation[] }

const empty: Database = { users: [], projects: [], friendRequests: [], friendships: [], invitations: [] }

function safeHandle(value: string, fallback: string) {
  const normalized = value.normalize('NFKD').toLowerCase().replace(/[^a-z0-9_-]/g, '').slice(0, 18)
  return normalized || `user-${fallback.slice(0, 8)}`
}

function publicProject(project: StoredProject, userId: string) {
  return {
    id: project.id,
    name: project.name,
    ownerId: project.ownerId,
    role: project.members.find((member) => member.userId === userId)?.role || 'viewer',
    updatedAt: project.updatedAt
  }
}

export class Store {
  private file = join(config.dataDir, 'store.json')
  private data: Database = structuredClone(empty)
  private queue = Promise.resolve()

  async init() {
    await mkdir(dirname(this.file), { recursive: true })
    try {
      this.data = { ...structuredClone(empty), ...JSON.parse(await readFile(this.file, 'utf8')) }
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error
      await this.persist()
    }
  }

  private persist() {
    this.queue = this.queue.then(async () => {
      const temporary = `${this.file}.tmp`
      await writeFile(temporary, JSON.stringify(this.data, null, 2), 'utf8')
      await rename(temporary, this.file)
    })
    return this.queue
  }

  userById(id: string) { return this.data.users.find((user) => user.id === id) }
  projectById(id: string) { return this.data.projects.find((project) => project.id === id) }
  canAccessProject(projectId: string, userId: string) { return Boolean(this.projectById(projectId)?.members.some((member) => member.userId === userId)) }

  async upsertUser(input: { provider: Provider; providerId: string; displayName: string; avatarUrl?: string }) {
    let user = this.data.users.find((item) => item.provider === input.provider && item.providerId === input.providerId)
    if (user) {
      user.displayName = input.displayName
      user.avatarUrl = input.avatarUrl
    } else {
      const id = randomUUID()
      const base = safeHandle(input.displayName, id)
      let handle = base
      let suffix = 1
      while (this.data.users.some((item) => item.handle === handle)) handle = `${base.slice(0, 15)}-${suffix++}`
      user = { id, ...input, handle, createdAt: new Date().toISOString() }
      this.data.users.push(user)
    }
    await this.persist()
    return user
  }

  listProjects(userId: string) {
    return this.data.projects.filter((project) => project.members.some((member) => member.userId === userId))
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).map((project) => publicProject(project, userId))
  }

  async createProject(userId: string, name: string) {
    const now = new Date().toISOString()
    const escapedTitle = name.replace(/[{}\\]/g, '')
    const project: StoredProject = {
      id: randomUUID(), name, ownerId: userId, members: [{ userId, role: 'owner' }], createdAt: now, updatedAt: now,
      mainTex: `\\documentclass[UTF8]{ctexart}\n\\usepackage{amsmath,amssymb,graphicx}\n\\title{${escapedTitle}}\n\\author{}\n\\date{\\today}\n\n\\begin{document}\n\\maketitle\n\n\\section{引言}\n从这里开始编写正文。\n\n\\end{document}\n`
    }
    this.data.projects.push(project)
    await this.persist()
    return publicProject(project, userId)
  }

  async createInvitation(projectId: string, userId: string) {
    const project = this.projectById(projectId)
    if (!project || project.ownerId !== userId) throw new Error('只有项目所有者可以创建邀请。')
    const invitation = { token: randomBytes(24).toString('base64url'), projectId, createdBy: userId, expiresAt: new Date(Date.now() + 7 * 86400_000).toISOString() }
    this.data.invitations.push(invitation)
    await this.persist()
    return invitation
  }

  async acceptInvitation(token: string, userId: string) {
    const invitation = this.data.invitations.find((item) => item.token === token)
    if (!invitation || new Date(invitation.expiresAt).getTime() < Date.now()) throw new Error('邀请链接无效或已过期。')
    const project = this.projectById(invitation.projectId)
    if (!project) throw new Error('项目不存在。')
    if (!project.members.some((member) => member.userId === userId)) project.members.push({ userId, role: 'editor' })
    project.updatedAt = new Date().toISOString()
    await this.persist()
    return publicProject(project, userId)
  }

  searchUsers(userId: string, query: string) {
    const needle = query.toLowerCase()
    const friendIds = new Set(this.data.friendships.flatMap((item) => item.leftId === userId ? [item.rightId] : item.rightId === userId ? [item.leftId] : []))
    return this.data.users.filter((user) => user.id !== userId && !friendIds.has(user.id) && (user.handle.toLowerCase().includes(needle) || user.displayName.toLowerCase().includes(needle))).slice(0, 12)
  }

  listFriends(userId: string) {
    const friendIds = this.data.friendships.flatMap((item) => item.leftId === userId ? [item.rightId] : item.rightId === userId ? [item.leftId] : [])
    const friends = friendIds.map((id) => this.userById(id)).filter(Boolean) as StoredUser[]
    const requests = this.data.friendRequests.filter((item) => item.status === 'pending' && (item.fromId === userId || item.toId === userId)).map((item) => ({
      id: item.id,
      direction: item.toId === userId ? 'incoming' as const : 'outgoing' as const,
      status: 'pending' as const,
      user: this.userById(item.toId === userId ? item.fromId : item.toId)!,
      createdAt: item.createdAt
    })).filter((item) => item.user)
    return { friends, requests }
  }

  async requestFriend(fromId: string, toId: string) {
    if (fromId === toId || !this.userById(toId)) throw new Error('用户不存在。')
    const exists = this.data.friendRequests.some((item) => item.status === 'pending' && ((item.fromId === fromId && item.toId === toId) || (item.fromId === toId && item.toId === fromId)))
    const alreadyFriends = this.data.friendships.some((item) => [item.leftId, item.rightId].includes(fromId) && [item.leftId, item.rightId].includes(toId))
    if (!exists && !alreadyFriends) this.data.friendRequests.push({ id: randomUUID(), fromId, toId, status: 'pending', createdAt: new Date().toISOString() })
    await this.persist()
  }

  async acceptFriend(userId: string, requestId: string) {
    const request = this.data.friendRequests.find((item) => item.id === requestId && item.toId === userId && item.status === 'pending')
    if (!request) throw new Error('好友申请不存在。')
    request.status = 'accepted'
    this.data.friendships.push({ id: randomUUID(), leftId: request.fromId, rightId: request.toId, createdAt: new Date().toISOString() })
    await this.persist()
  }
}
