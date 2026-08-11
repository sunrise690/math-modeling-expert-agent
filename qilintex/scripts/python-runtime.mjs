import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

export const qilintexRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
export const repositoryRoot = resolve(qilintexRoot, '..')
export const runtimePython = process.platform === 'win32'
  ? resolve(repositoryRoot, '.runtime', 'python', 'Scripts', 'python.exe')
  : resolve(repositoryRoot, '.runtime', 'python', 'bin', 'python')

function candidates() {
  const configured = process.env.PYTHON?.trim()
  return [
    ...(existsSync(runtimePython) ? [{ command: runtimePython, prefix: [] }] : []),
    ...(configured ? [{ command: configured, prefix: [] }] : []),
    ...(process.platform === 'win32'
      ? [{ command: 'py', prefix: ['-3'] }, { command: 'python', prefix: [] }]
      : [{ command: 'python3', prefix: [] }, { command: 'python', prefix: [] }])
  ]
}

export function findPython({ preferManaged = true } = {}) {
  for (const candidate of candidates()) {
    if (!preferManaged && candidate.command === runtimePython) continue
    const probe = spawnSync(candidate.command, [...candidate.prefix, '-c', 'import sys; raise SystemExit(sys.version_info < (3, 11))'], {
      encoding: 'utf8',
      stdio: 'ignore',
      windowsHide: true
    })
    if (!probe.error && probe.status === 0) return candidate
  }
  throw new Error('未找到 Python 3.11 或更高版本。请先安装兼容版本，或通过 PYTHON 指定解释器。')
}
