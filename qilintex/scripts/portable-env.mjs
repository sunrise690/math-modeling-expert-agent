import { existsSync, readFileSync } from 'node:fs'

function parseLine(rawLine) {
  const line = rawLine.trim()
  if (!line || line.startsWith('#')) return null
  const separator = line.indexOf('=')
  if (separator < 1) return null
  const key = line.slice(0, separator).trim()
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) return null
  let value = line.slice(separator + 1).trim()
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    value = value.slice(1, -1)
  }
  return [key, value]
}

export function loadPortableEnv(paths) {
  for (const path of paths) {
    if (!existsSync(path)) continue
    for (const rawLine of readFileSync(path, 'utf8').replace(/^\uFEFF/, '').split(/\r?\n/)) {
      const entry = parseLine(rawLine)
      if (!entry) continue
      const [key, value] = entry
      if (process.env[key] === undefined) process.env[key] = value
    }
  }
}
