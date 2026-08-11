import { describe, expect, it } from 'vitest'
import { invitationFromSearch, realmFromHash, sessionFromHash } from './urls'

describe('登录与邀请链接', () => {
  it('从 URL 片段读取会话并正确解码', () => {
    expect(sessionFromHash('#session=a.b%2Fc')).toBe('a.b/c')
    expect(realmFromHash('#session=a.b&realm=oauth')).toBe('oauth')
    expect(realmFromHash('#session=a.b')).toBe('team')
  })

  it('从查询参数读取项目邀请', () => {
    expect(invitationFromSearch('?invite=invite-token')).toBe('invite-token')
  })
})
