import { beforeEach, describe, expect, it } from 'vitest'
import { getAuthRealm, getToken, setAuthRealm, setToken } from './api'

class MemoryStorage implements Storage {
  private values = new Map<string, string>()
  get length() { return this.values.size }
  clear() { this.values.clear() }
  getItem(key: string) { return this.values.get(key) ?? null }
  key(index: number) { return [...this.values.keys()][index] ?? null }
  removeItem(key: string) { this.values.delete(key) }
  setItem(key: string, value: string) { this.values.set(key, value) }
}

describe('客户端登录域隔离', () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, 'localStorage', { value: new MemoryStorage(), configurable: true })
  })

  it('分别保存团队与 OAuth token，清理一方不影响另一方', () => {
    setAuthRealm('team')
    setToken('team-token')
    setAuthRealm('oauth')
    setToken('oauth-token')

    expect(getAuthRealm()).toBe('oauth')
    expect(getToken('team')).toBe('team-token')
    expect(getToken('oauth')).toBe('oauth-token')

    setToken(undefined, 'team')
    expect(getToken('team')).toBe('')
    expect(getToken('oauth')).toBe('oauth-token')
  })
})
