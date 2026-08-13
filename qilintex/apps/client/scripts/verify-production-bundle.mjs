import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const distRoot = fileURLToPath(new URL('../dist/', import.meta.url))
const forbiddenAddresses = ['http://localhost:4318', 'ws://localhost:4319']
const requiredPublicAddresses = ['https://updates.qilintex.top/']
const landingSource = await readFile(fileURLToPath(new URL('../src/components/Landing.tsx', import.meta.url)), 'utf8')
const styleSource = await readFile(fileURLToPath(new URL('../src/styles.css', import.meta.url)), 'utf8')
const workbenchSourcePaths = [
  '../src/App.tsx',
  '../src/components/Workbench.tsx',
  '../src/components/ApiSettings.tsx',
  '../src/components/UpdateButton.tsx'
]
const workbenchSources = await Promise.all(workbenchSourcePaths.map((path) => readFile(fileURLToPath(new URL(path, import.meta.url)), 'utf8')))
const forbiddenLandingShells = ['entry-titlebar', 'entry-activity', 'entry-sidebar', 'entry-tabs', 'entry-statusbar']
const requiredLandingContent = ['在线使用', '下载应用', 'Qilintex-Setup-', 'Qilintex-Portable-']
const requiredLandingStyle = ['--entry-bg: #181818', '--entry-surface: #1f1f1f', '--entry-accent: #0078d4', '--entry-radius: 10px', '--entry-radius-lg: 14px']
const forbiddenWorkbenchDownloads = ['/downloads', 'updates.qilintex.top', '下载应用', '下载 App', '下载安装包']

async function filesUnder(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const nested = await Promise.all(entries.map((entry) => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? filesUnder(path) : [path]
  }))
  return nested.flat()
}

const files = await filesUnder(distRoot)
for (const path of files.filter((item) => /\.(?:html|js|css|json|webmanifest)$/.test(item))) {
  const content = await readFile(path, 'utf8')
  const forbidden = forbiddenAddresses.find((address) => content.includes(address))
  if (forbidden) {
    throw new Error(`生产前端仍包含本机地址 ${forbidden}：${path}`)
  }
}

const bundleText = (await Promise.all(files.filter((item) => /\.js$/.test(item)).map((path) => readFile(path, 'utf8')))).join('\n')
for (const address of requiredPublicAddresses) {
  if (!bundleText.includes(address)) throw new Error(`生产前端缺少正式地址 ${address}`)
}

for (const className of forbiddenLandingShells) {
  if (landingSource.includes(className)) throw new Error(`公开入口不得包含无功能的编辑器外壳：${className}`)
}

for (const content of requiredLandingContent) {
  if (!landingSource.includes(content)) throw new Error(`公开入口缺少必要的在线/下载内容：${content}`)
}

for (const token of requiredLandingStyle) {
  if (!styleSource.includes(token)) throw new Error(`公开入口偏离深色小圆角视觉基线：${token}`)
}

for (const [index, source] of workbenchSources.entries()) {
  const forbidden = forbiddenWorkbenchDownloads.find((content) => source.includes(content))
  if (forbidden) throw new Error(`在线任务界面不得包含客户端导流：${forbidden}（来源 ${workbenchSourcePaths[index]}）`)
}

if (!workbenchSources.at(-1)?.includes('Capacitor.isNativePlatform()')) {
  throw new Error('移动端更新入口必须由原生运行环境保护')
}

console.log('生产前端已通过同源地址、公开页双入口与在线任务界面无下载能力检查')
