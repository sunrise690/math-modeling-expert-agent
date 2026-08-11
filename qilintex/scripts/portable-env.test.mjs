import assert from 'node:assert/strict'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import { loadPortableEnv } from './portable-env.mjs'

test('按显式环境、局部配置、根配置的顺序解析', () => {
  const directory = mkdtempSync(join(tmpdir(), 'modeling-workbench-env-'))
  const local = join(directory, 'local.env')
  const root = join(directory, 'root.env')
  const keys = ['PORTABLE_ENV_PRIORITY', 'PORTABLE_ENV_ROOT_ONLY', 'PORTABLE_ENV_QUOTED']
  try {
    writeFileSync(local, 'PORTABLE_ENV_PRIORITY=local\nPORTABLE_ENV_QUOTED="中文路径"\n', 'utf8')
    writeFileSync(root, 'PORTABLE_ENV_PRIORITY=root\nPORTABLE_ENV_ROOT_ONLY=available\n', 'utf8')
    process.env.PORTABLE_ENV_PRIORITY = 'process'
    loadPortableEnv([local, root])
    assert.equal(process.env.PORTABLE_ENV_PRIORITY, 'process')
    assert.equal(process.env.PORTABLE_ENV_ROOT_ONLY, 'available')
    assert.equal(process.env.PORTABLE_ENV_QUOTED, '中文路径')
  } finally {
    for (const key of keys) delete process.env[key]
    rmSync(directory, { recursive: true, force: true })
  }
})
