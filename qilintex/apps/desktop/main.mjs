import { app, BrowserWindow, ipcMain, shell } from 'electron'
import { autoUpdater } from 'electron-updater'
import { spawn } from 'node:child_process'
import { appendFileSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parseDeepLink } from './protocol.mjs'

const currentDir = fileURLToPath(new URL('.', import.meta.url))
const DEFAULT_WORKBENCH_URL = 'http://62.234.109.41/'
const LOCAL_AGENT_URL = 'http://127.0.0.1:8765'
const MAX_IPC_BODY_BYTES = 30 * 1024 * 1024
const MAX_IPC_RESPONSE_BYTES = 110 * 1024 * 1024

let mainWindow
let agentProcess
let updateState = { status: 'idle' }
let pendingTicket = ''
let quitting = false

function diagnostic(message) {
  try { appendFileSync(join(app.getPath('userData'), 'desktop.log'), `${new Date().toISOString()} ${message}\n`, 'utf8') } catch { /* 日志不能影响应用启动 */ }
}

function workbenchUrl() {
  const configured = process.env.WORKBENCH_URL || process.env.VITE_DEV_SERVER_URL || DEFAULT_WORKBENCH_URL
  const parsed = new URL(configured)
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) throw new Error('WORKBENCH_URL 必须是有效的 HTTP(S) 地址。')
  return parsed.toString()
}

function agentRuntimePaths() {
  if (app.isPackaged) {
    return {
      python: join(process.resourcesPath, 'runtime', 'python', 'python.exe'),
      server: join(process.resourcesPath, 'agent', 'server.py')
    }
  }
  const repositoryRoot = resolve(currentDir, '..', '..', '..')
  return {
    python: process.env.AGENT_PYTHON || join(repositoryRoot, '.runtime', 'python', 'Scripts', 'python.exe'),
    server: join(repositoryRoot, 'server.py')
  }
}

function startLocalAgent() {
  if (agentProcess || quitting) return
  const runtime = agentRuntimePaths()
  diagnostic(`local agent runtime: python=${runtime.python}, server=${runtime.server}`)
  if (!existsSync(runtime.python) || !existsSync(runtime.server)) {
    diagnostic('local agent runtime files are missing')
    return
  }
  const frontend = workbenchUrl()
  agentProcess = spawn(runtime.python, [runtime.server, '--host', '127.0.0.1', '--port', '8765', '--frontend-url', frontend], {
    cwd: app.isPackaged ? join(process.resourcesPath, 'agent') : resolve(currentDir, '..', '..', '..'),
    env: {
      ...process.env,
      AGENT_DATA_DIR: join(app.getPath('userData'), 'agent-data'),
      CODEX_LOGIN_FLOW: 'browser',
      PYTHONUTF8: '1',
      PYTHONUNBUFFERED: '1'
    },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe']
  })
  agentProcess.once('spawn', () => diagnostic(`local agent spawned: pid=${agentProcess.pid}`))
  agentProcess.once('error', (error) => diagnostic(`local agent error: ${error.message}`))
  agentProcess.stdout?.on('data', (chunk) => diagnostic(`agent: ${String(chunk).trim()}`))
  agentProcess.stderr?.on('data', (chunk) => diagnostic(`agent error: ${String(chunk).trim()}`))
  agentProcess.on('exit', (code) => {
    diagnostic(`local agent exited: code=${code}`)
    agentProcess = undefined
    if (!quitting) setTimeout(startLocalAgent, 1500)
  })
}

function isAllowedAgentRequest(path, method) {
  if (typeof path !== 'string' || path.length > 500 || path.includes('?') || path.includes('#')) return false
  const rules = [
    ['GET', /^\/api\/(?:health|config)$/],
    ['POST', /^\/api\/(?:config|config\/test|codex-login|uploads|runs)$/],
    ['GET', /^\/api\/codex-login\/[a-f0-9]{32}$/],
    ['DELETE', /^\/api\/codex-login\/[a-f0-9]{32}$/],
    ['DELETE', /^\/api\/uploads\/[a-f0-9]{32}$/],
    ['GET', /^\/api\/runs\/[a-f0-9]{32}$/],
    ['POST', /^\/api\/runs\/[a-f0-9]{32}\/cancel$/],
    ['GET', /^\/api\/runs\/[a-f0-9]{32}\/artifacts$/],
    ['GET', /^\/api\/artifacts\/[a-f0-9]{32}\/[A-Za-z0-9._~%+-]+$/]
  ]
  return rules.some(([allowedMethod, pattern]) => allowedMethod === method && pattern.test(path))
}

function sendUpdate(state) {
  updateState = { ...updateState, ...state }
  mainWindow?.webContents.send('updates:state', updateState)
}

function readDeepLink(args) {
  const link = parseDeepLink(args)
  if (!link) return
  pendingTicket = link.ticket
  if (mainWindow?.webContents) mainWindow.webContents.send('auth:ticket', link.ticket)
  mainWindow?.show()
  mainWindow?.focus()
}

function registerProtocol() {
  if (process.defaultApp && process.argv[1]) app.setAsDefaultProtocolClient('tonggaotex', process.execPath, [resolve(process.argv[1])])
  else app.setAsDefaultProtocolClient('tonggaotex')
}

function createWindow() {
  const frontend = workbenchUrl()
  const frontendOrigin = new URL(frontend).origin
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 920,
    minWidth: 980,
    minHeight: 650,
    backgroundColor: '#181818',
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(currentDir, 'preload.mjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) void shell.openExternal(url)
    return { action: 'deny' }
  })
  mainWindow.webContents.on('will-navigate', (event, url) => {
    let targetOrigin = ''
    try { targetOrigin = new URL(url).origin } catch { /* 无效地址按外部地址处理 */ }
    if (targetOrigin !== frontendOrigin) {
      event.preventDefault()
      if (/^https?:/.test(url)) void shell.openExternal(url)
    }
  })

  void mainWindow.loadURL(frontend)
  mainWindow.webContents.on('did-finish-load', () => {
    if (pendingTicket) mainWindow.webContents.send('auth:ticket', pendingTicket)
  })
}

autoUpdater.autoDownload = true
autoUpdater.autoInstallOnAppQuit = true
autoUpdater.on('checking-for-update', () => sendUpdate({ status: 'checking' }))
autoUpdater.on('update-available', (info) => sendUpdate({ status: 'available', version: info.version }))
autoUpdater.on('update-not-available', () => sendUpdate({ status: 'current', version: app.getVersion() }))
autoUpdater.on('download-progress', (progress) => sendUpdate({ status: 'downloading', percent: progress.percent }))
autoUpdater.on('update-downloaded', (info) => sendUpdate({ status: 'downloaded', version: info.version, percent: 100 }))
autoUpdater.on('error', (error) => sendUpdate({ status: 'error', message: error.message }))

ipcMain.handle('external:open', async (_event, url) => {
  const parsed = new URL(url)
  if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('不允许打开该协议。')
  await shell.openExternal(url)
})
ipcMain.handle('agent:request', async (_event, request) => {
  const method = String(request?.method || 'GET').toUpperCase()
  const path = String(request?.path || '')
  if (!isAllowedAgentRequest(path, method)) throw new Error('本机运行器请求不在允许列表中。')
  const body = request?.bodyBase64 ? Buffer.from(String(request.bodyBase64), 'base64') : undefined
  if (body && body.byteLength > MAX_IPC_BODY_BYTES) throw new Error('提交内容超过本机运行器限制。')
  const headers = new Headers()
  for (const [name, value] of Object.entries(request?.headers || {})) {
    if (['accept', 'content-type', 'x-filename'].includes(name.toLowerCase())) headers.set(name, String(value))
  }
  let response
  try {
    response = await fetch(`${LOCAL_AGENT_URL}${path}`, {
      method,
      headers,
      body,
      redirect: 'error',
      signal: AbortSignal.timeout(120_000)
    })
  } catch {
    throw new Error('本机运行器尚未就绪，请稍候重试或重新打开 Qilintex。')
  }
  const bytes = Buffer.from(await response.arrayBuffer())
  if (bytes.byteLength > MAX_IPC_RESPONSE_BYTES) throw new Error('本机运行器返回内容过大。')
  return {
    ok: response.ok,
    status: response.status,
    headers: Object.fromEntries(response.headers.entries()),
    bodyBase64: bytes.toString('base64')
  }
})
ipcMain.handle('updates:get-state', () => updateState)
ipcMain.handle('updates:check', async () => {
  if (!app.isPackaged) return (updateState = { status: 'unsupported', message: '开发模式不检查更新。' })
  if (process.env.UPDATE_URL) autoUpdater.setFeedURL({ provider: 'generic', url: process.env.UPDATE_URL })
  await autoUpdater.checkForUpdates()
  return updateState
})
ipcMain.handle('updates:install', () => autoUpdater.quitAndInstall(false, true))

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) app.quit()
else {
  app.on('second-instance', (_event, argv) => readDeepLink(argv))
  app.on('open-url', (event, url) => { event.preventDefault(); readDeepLink([url]) })
  app.whenReady().then(() => {
    diagnostic(`desktop ready: version=${app.getVersion()}, packaged=${app.isPackaged}`)
    registerProtocol()
    startLocalAgent()
    createWindow()
    readDeepLink(process.argv)
    app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })
  })
  app.on('before-quit', () => {
    quitting = true
    agentProcess?.kill()
  })
  app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
}
