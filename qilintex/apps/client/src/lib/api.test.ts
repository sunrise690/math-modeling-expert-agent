import { beforeEach, describe, expect, it } from 'vitest'
import { getAuthRealm, getToken, resolveServiceUrls, setAuthRealm, setToken } from './api'

class MemoryStorage implements Storage {
  private values = new Map<string, string>()
  get length() { return this.values.size }
  clear() { this.values.clear() }
  getItem(key: string) { return this.values.get(key) ?? null }
  key(index: number) { return [...this.values.keys()][index] ?? null }
  removeItem(key: string) { this.values.delete(key) }
  setItem(key: string, value: string) { this.values.set(key, value) }
}

describe('可移植服务地址', () => {
  it('生产 Web 端默认使用当前站点同源 API 和协作通道', () => {
    expect(resolveServiceUrls('', '', { protocol: 'http:', host: '62.234.109.41' })).toEqual({
      apiUrl: '',
      collabUrl: 'ws://62.234.109.41/collab'
    })
    expect(resolveServiceUrls('', '', { protocol: 'https:', host: 'modeling.example' })).toEqual({
      apiUrl: '',
      collabUrl: 'wss://modeling.example/collab'
    })
  })

  it('桌面端保持本机内嵌服务，显式配置仍可覆盖默认值', () => {
    expect(resolveServiceUrls('', '', { protocol: 'file:', host: '' })).toEqual({
      apiUrl: 'http://127.0.0.1:4318',
      collabUrl: 'ws://127.0.0.1:4319'
    })
    expect(resolveServiceUrls('https://api.example/', 'wss://collab.example/socket/')).toEqual({
      apiUrl: 'https://api.example',
      collabUrl: 'wss://collab.example/socket'
    })
  })
})

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
