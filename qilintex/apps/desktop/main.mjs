import { app, BrowserWindow, ipcMain, shell } from 'electron'
import { autoUpdater } from 'electron-updater'
import { spawn } from 'node:child_process'
import { appendFileSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parseDeepLink } from './protocol.mjs'

const currentDir = fileURLToPath(new URL('.', import.meta.url))
let mainWindow
let serverProcess
let updateState = { status: 'idle' }
let pendingTicket = ''

function diagnostic(message) {
  try { appendFileSync(join(app.getPath('userData'), 'desktop.log'), `${new Date().toISOString()} ${message}\n`, 'utf8') } catch { /* logging must never stop the app */ }
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

function startEmbeddedServer() {
  if (process.env.VITE_DEV_SERVER_URL || process.env.TONGGAO_EMBED_SERVER === 'false') {
    diagnostic(`embedded server skipped: packaged=${app.isPackaged}`)
    return
  }
  const bundle = join(process.resourcesPath, 'server', 'bundle.cjs')
  diagnostic(`embedded bundle: ${bundle}, exists=${existsSync(bundle)}`)
  if (!existsSync(bundle)) return
  serverProcess = spawn(process.execPath, [bundle], {
    env: {
      ...process.env,
      ELECTRON_RUN_AS_NODE: '1',
      NODE_ENV: 'production',
      ALLOW_DEV_LOGIN: process.env.ALLOW_DEV_LOGIN || 'true',
      DATA_DIR: join(app.getPath('userData'), 'server-data'),
      CLIENT_URL: 'file://',
      PORT: process.env.PORT || '4318',
      COLLAB_PORT: process.env.COLLAB_PORT || '4319'
    },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe']
  })
  serverProcess.once('spawn', () => diagnostic(`embedded server spawned: pid=${serverProcess.pid}`))
  serverProcess.once('error', (error) => diagnostic(`embedded server error: ${error.message}`))
  serverProcess.stdout?.on('data', (chunk) => diagnostic(`server: ${String(chunk).trim()}`))
  serverProcess.stderr?.on('data', (chunk) => diagnostic(`server error: ${String(chunk).trim()}`))
  serverProcess.on('exit', (code) => {
    diagnostic(`embedded server exited: code=${code}`)
    if (code && mainWindow) mainWindow.webContents.send('server:state', { status: 'error', code })
  })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 920,
    minWidth: 980,
    minHeight: 650,
    backgroundColor: '#FFFFFF',
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(currentDir, 'preload.mjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) shell.openExternal(url)
    return { action: 'deny' }
  })
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith('file:') && !url.startsWith(process.env.VITE_DEV_SERVER_URL || 'http://localhost:5173')) {
      event.preventDefault()
      shell.openExternal(url)
    }
  })

  if (process.env.VITE_DEV_SERVER_URL) mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
  else mainWindow.loadFile(join(process.resourcesPath, 'web', 'index.html'))

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
    startEmbeddedServer()
    createWindow()
    readDeepLink(process.argv)
    app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })
  })
  app.on('before-quit', () => serverProcess?.kill())
  app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
}
