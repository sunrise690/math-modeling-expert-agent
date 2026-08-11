import { describe, expect, it } from 'vitest'
import { isNewerVersion } from './UpdateButton'

describe('应用版本比较', () => {
  it('识别更高版本', () => expect(isNewerVersion('0.1.9', '0.2.0')).toBe(true))
  it('忽略相同或更低版本', () => {
    expect(isNewerVersion('1.2.0', '1.2')).toBe(false)
    expect(isNewerVersion('2.0.0', '1.9.9')).toBe(false)
  })
})
