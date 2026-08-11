import test from 'node:test'
import assert from 'node:assert/strict'
import { parseDeepLink } from '../protocol.mjs'

test('解析桌面 OAuth 一次性 ticket', () => {
  assert.deepEqual(parseDeepLink(['--flag', 'tonggaotex://auth?ticket=once%2Fonly']), { type: 'auth', ticket: 'once/only' })
})

test('拒绝无 ticket 或其他协议', () => {
  assert.equal(parseDeepLink(['https://example.com']), null)
  assert.equal(parseDeepLink(['tonggaotex://auth']), null)
})
