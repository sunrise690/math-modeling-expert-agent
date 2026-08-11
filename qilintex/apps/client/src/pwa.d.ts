declare module 'virtual:pwa-register/react' {
  export function useRegisterSW(options?: Record<string, unknown>): {
    needRefresh: [boolean, (value: boolean) => void]
    offlineReady: [boolean, (value: boolean) => void]
    updateServiceWorker: (reloadPage?: boolean) => Promise<void>
  }
}
