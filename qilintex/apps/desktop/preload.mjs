import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('desktop', {
  platform: process.platform,
  openExternal: (url) => ipcRenderer.invoke('external:open', url),
  getUpdateState: () => ipcRenderer.invoke('updates:get-state'),
  checkForUpdates: () => ipcRenderer.invoke('updates:check'),
  installUpdate: () => ipcRenderer.invoke('updates:install'),
  onUpdateState: (callback) => {
    const listener = (_event, state) => callback(state)
    ipcRenderer.on('updates:state', listener)
    return () => ipcRenderer.removeListener('updates:state', listener)
  },
  onAuthTicket: (callback) => {
    const listener = (_event, ticket) => callback(ticket)
    ipcRenderer.on('auth:ticket', listener)
    return () => ipcRenderer.removeListener('auth:ticket', listener)
  }
})
