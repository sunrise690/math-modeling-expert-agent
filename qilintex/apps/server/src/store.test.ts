import { describe, expect, it } from 'vitest'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { Store, toPublicUser, type StoredUser } from './store.js'
import { compileLatex } from './compiler.js'
import { authRealmForProvider, matchesAccessCode, normalizeTeamAccountId, signSession, verifySession, verifySessionDetails } from './auth.js'

describe('服务端数据边界', () => {
  it('公开用户对象不泄露开放平台标识', () => {
    const user: StoredUser = {
      id: 'user-id', provider: 'qq', providerId: 'private-openid', handle: 'member', displayName: '成员', createdAt: new Date(0).toISOString()
    }
    expect(toPublicUser(user)).toEqual({ id: 'user-id', provider: 'qq', handle: 'member', displayName: '成员', avatarUrl: undefined })
    expect(toPublicUser(user)).not.toHaveProperty('providerId')
  })

  it('拒绝编译空文档', async () => {
    await expect(compileLatex('   ')).resolves.toMatchObject({ ok: false, log: 'main.tex 为空。' })
  })

  it('以常量时间摘要校验团队口令，并允许开发环境空口令', () => {
    expect(matchesAccessCode('model-2026', 'model-2026')).toBe(true)
    expect(matchesAccessCode('wrong', 'model-2026')).toBe(false)
    expect(matchesAccessCode('', '')).toBe(true)
  })

  it('规范化唯一账号 ID 并拒绝无效 ID', () => {
    expect(normalizeTeamAccountId(' Alice_01 ')).toBe('alice_01')
    expect(() => normalizeTeamAccountId('ab')).toThrow('3–24')
    expect(() => normalizeTeamAccountId('中文账号')).toThrow('3–24')
  })

  it('同一个团队账号 ID 在不同登录中始终返回同一账号', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'qilintex-account-'))
    try {
      const store = new Store(directory)
      await store.init()
      const first = await store.loginTeamUser('alice', 'alice@example.com')
      const second = await store.loginTeamUser('alice')
      expect(second.id).toBe(first.id)
      expect(second.handle).toBe('alice')
      expect(second.email).toBe('alice@example.com')
    } finally {
      await rm(directory, { recursive: true, force: true })
    }
  })

  it('保存个人资料并保持账号 ID 不变，同时拒绝重复邮箱', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'qilintex-profile-'))
    try {
      const store = new Store(directory)
      await store.init()
      const alice = await store.loginTeamUser('alice', 'alice@example.com')
      await store.loginTeamUser('bob', 'bob@example.com')
      const updated = await store.updateUserProfile(alice.id, {
        displayName: 'Alice 队长', email: 'captain@example.com', avatarUrl: 'https://example.com/avatar.png'
      })
      expect(updated).toMatchObject({ handle: 'alice', displayName: 'Alice 队长', email: 'captain@example.com' })
      await expect(store.updateUserProfile(alice.id, { displayName: 'Alice', email: 'bob@example.com' })).rejects.toThrow('已绑定其他账号')
    } finally {
      await rm(directory, { recursive: true, force: true })
    }
  })

  it('团队会话与开放平台会话互相拒绝', async () => {
    const teamUser: StoredUser = {
      id: 'team-user', provider: 'team', providerId: 'device', handle: 'team-user', displayName: '队员', createdAt: new Date(0).toISOString()
    }
    const oauthUser: StoredUser = {
      id: 'qq-user', provider: 'qq', providerId: 'openid', handle: 'qq-user', displayName: 'QQ 用户', createdAt: new Date(0).toISOString()
    }
    const teamToken = await signSession(teamUser)
    const oauthToken = await signSession(oauthUser)

    await expect(verifySession(teamToken, 'team')).resolves.toBe(teamUser.id)
    await expect(verifySession(oauthToken, 'oauth')).resolves.toBe(oauthUser.id)
    await expect(verifySession(teamToken, 'oauth')).rejects.toThrow('登录方式不匹配')
    await expect(verifySession(oauthToken, 'team')).rejects.toThrow('登录方式不匹配')
    await expect(verifySessionDetails(teamToken)).resolves.toMatchObject({ realm: 'team', provider: 'team' })
    expect(authRealmForProvider('wechat')).toBe('oauth')
  })

  it('完整返回收到和发出的好友申请，并允许收件人接受', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'qilintex-friends-'))
    try {
      const store = new Store(directory)
      await store.init()
      const alice = await store.upsertUser({ provider: 'team', providerId: 'alice-device', displayName: 'Alice' })
      const bob = await store.upsertUser({ provider: 'team', providerId: 'bob-device', displayName: 'Bob' })

      await store.requestFriend(alice.id, bob.id)
      expect(store.searchUsers(alice.id, 'Bob')).toEqual([])

      const outgoing = store.listFriends(alice.id).requests
      const incoming = store.listFriends(bob.id).requests
      expect(outgoing).toHaveLength(1)
      expect(outgoing[0]).toMatchObject({ direction: 'outgoing', user: { id: bob.id } })
      expect(incoming).toHaveLength(1)
      expect(incoming[0]).toMatchObject({ direction: 'incoming', user: { id: alice.id } })

      await store.acceptFriend(bob.id, incoming[0].id)
      expect(store.listFriends(alice.id).friends.map((user) => user.id)).toContain(bob.id)
      expect(store.listFriends(bob.id).friends.map((user) => user.id)).toContain(alice.id)
      expect(store.listFriends(bob.id).requests).toEqual([])

      const sent = await store.sendDirectMessage(alice.id, bob.id, '你好，开始建模吗？')
      expect(store.listDirectMessages(bob.id, alice.id)).toEqual([sent])
    } finally {
      await rm(directory, { recursive: true, force: true })
    }
  })
})
