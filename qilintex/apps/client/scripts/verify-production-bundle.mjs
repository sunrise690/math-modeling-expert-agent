import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const distRoot = fileURLToPath(new URL('../dist/', import.meta.url))
const forbiddenAddresses = ['http://localhost:4318', 'ws://localhost:4319']
const requiredPublicAddresses = ['https://updates.qilintex.top/']
const landingSource = await readFile(fileURLToPath(new URL('../src/components/Landing.tsx', import.meta.url)), 'utf8')
const forbiddenLandingShells = ['entry-titlebar', 'entry-activity', 'entry-sidebar', 'entry-tabs', 'entry-statusbar']

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

console.log('生产前端已通过同源地址、正式在线/下载入口与纯净公开页检查')
