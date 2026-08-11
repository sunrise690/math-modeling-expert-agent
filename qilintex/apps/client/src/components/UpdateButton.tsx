import { useEffect, useState } from 'react'
import { Download, RefreshCw } from 'lucide-react'
import { Capacitor } from '@capacitor/core'
import { App as CapacitorApp } from '@capacitor/app'
import { Browser } from '@capacitor/browser'
import { apiUrl } from '../lib/api'

export function isNewerVersion(current: string, latest: string) {
  const left = current.split('.').map((part) => Number.parseInt(part, 10) || 0)
  const right = latest.split('.').map((part) => Number.parseInt(part, 10) || 0)
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    if ((right[index] || 0) > (left[index] || 0)) return true
    if ((right[index] || 0) < (left[index] || 0)) return false
  }
  return false
}

export function UpdateButton() {
  const [desktopState, setDesktopState] = useState<UpdateState>({ status: 'idle' })
  const [mobileUpdate, setMobileUpdate] = useState<{ version: string; storeUrl: string } | null>(null)

  useEffect(() => {
    if (!window.desktop) return
    window.desktop.getUpdateState().then(setDesktopState)
    return window.desktop.onUpdateState(setDesktopState)
  }, [])

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return
    const check = async () => {
      const info = await CapacitorApp.getInfo()
      const platform = Capacitor.getPlatform()
      const response = await fetch(`${apiUrl}/updates/latest?platform=${encodeURIComponent(platform)}`)
      if (!response.ok) return
      const latest = await response.json() as { version: string; storeUrl: string }
      if (latest.storeUrl && isNewerVersion(info.version, latest.version)) setMobileUpdate(latest)
    }
    check().catch(() => undefined)
  }, [])

  if (window.desktop) {
    if (desktopState.status === 'downloaded') {
      return <button className="toolbar-button update-ready" onClick={() => window.desktop?.installUpdate()}><Download size={16} />重启更新</button>
    }
    const label = desktopState.status === 'checking' ? '检查中' : desktopState.status === 'downloading'
      ? `下载 ${Math.round(desktopState.percent || 0)}%` : desktopState.status === 'current' ? '已是最新版' : '检查更新'
    return <button className="toolbar-button" onClick={() => window.desktop?.checkForUpdates()} disabled={['checking', 'downloading'].includes(desktopState.status)}><RefreshCw size={16} className={desktopState.status === 'checking' ? 'spin' : ''} />{label}</button>
  }

  if (Capacitor.isNativePlatform() && mobileUpdate) {
    return <button className="toolbar-button update-ready" onClick={() => Browser.open({ url: mobileUpdate.storeUrl })}><Download size={16} />更新 {mobileUpdate.version}</button>
  }

  return null
}
