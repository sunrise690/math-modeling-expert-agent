import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'cn.tonggao.tex',
  appName: 'Qilintex',
  webDir: 'dist',
  server: { androidScheme: 'https' },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1200,
      backgroundColor: '#0F0F0F',
      showSpinner: false
    }
  }
}

export default config
