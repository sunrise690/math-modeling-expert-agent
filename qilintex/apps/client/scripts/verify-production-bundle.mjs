import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const distRoot = fileURLToPath(new URL('../dist/', import.meta.url))
const forbiddenAddresses = ['http://localhost:4318', 'ws://localhost:4319']

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

console.log('生产前端已通过同源地址检查')
