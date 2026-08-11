import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import { findPython, repositoryRoot, runtimePython } from './python-runtime.mjs'

function run(command, args) {
  const result = spawnSync(command, args, { cwd: repositoryRoot, stdio: 'inherit', windowsHide: true })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status ?? 1)
}

try {
  mkdirSync(resolve(repositoryRoot, '.runtime'), { recursive: true })
  const managed = findPython()
  if (managed.command !== runtimePython) {
    const system = findPython({ preferManaged: false })
    run(system.command, [...system.prefix, '-m', 'venv', resolve(repositoryRoot, '.runtime', 'python')])
  }
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`)
  process.exit(1)
}

run(runtimePython, ['-m', 'pip', 'install', '-r', resolve(repositoryRoot, 'requirements.txt')])
process.stdout.write(`Python 运行环境已准备：${runtimePython}\n`)
