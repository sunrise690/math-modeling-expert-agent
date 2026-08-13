import { resolve } from 'node:path'
import { spawn } from 'node:child_process'
import { findPython, qilintexRoot, repositoryRoot } from './python-runtime.mjs'
import { loadPortableEnv } from './portable-env.mjs'

loadPortableEnv([
  resolve(qilintexRoot, '.env'),
  resolve(repositoryRoot, '.env')
])

let python
try {
  python = findPython()
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n请先运行 pnpm setup。\n`)
  process.exit(1)
}

const frontendUrl = process.env.WORKBENCH_URL?.trim() || process.env.CLIENT_URL?.trim() || 'http://localhost:5173'
const configuredAgentUrl = process.env.MATH_MODELING_AGENT_URL?.trim() || 'http://127.0.0.1:8765'
let agentPort
try {
  const parsed = new URL(configuredAgentUrl)
  if (!['localhost', '127.0.0.1', '::1'].includes(parsed.hostname)) throw new Error('数模 Agent 只能绑定本机回环地址')
  agentPort = parsed.port || '8765'
} catch (error) {
  process.stderr.write(`MATH_MODELING_AGENT_URL 无效：${error instanceof Error ? error.message : String(error)}\n`)
  process.exit(1)
}
const child = spawn(python.command, [
  ...python.prefix,
  resolve(repositoryRoot, 'server.py'),
  '--port', agentPort,
  '--frontend-url', frontendUrl,
  '--allowed-origin', 'https://qilintex.top'
], {
  cwd: repositoryRoot,
  env: process.env,
  stdio: 'inherit',
  windowsHide: true
})

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill(signal))
}
child.on('error', (error) => {
  process.stderr.write(`数模 Agent 启动失败：${error.message}\n`)
  process.exit(1)
})
child.on('exit', (code, signal) => {
  if (signal) process.kill(process.pid, signal)
  else process.exit(code ?? 1)
})
