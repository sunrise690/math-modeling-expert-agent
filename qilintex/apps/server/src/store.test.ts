import { describe, expect, it } from 'vitest'
import { toPublicUser, type StoredUser } from './store.js'
import { compileLatex } from './compiler.js'
import { authRealmForProvider, matchesAccessCode, signSession, verifySession, verifySessionDetails } from './auth.js'

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
})
