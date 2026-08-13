import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

const httpConfig = await readFile(new URL('../deploy/Caddyfile.http', import.meta.url), 'utf8')
const httpsConfig = await readFile(new URL('../deploy/Caddyfile.https', import.meta.url), 'utf8')

function assertPublicDownloadsBlocked(config, name) {
  assert.match(config, /@downloads\s+path \/downloads \/downloads\/\*/u, `${name} 缺少下载路径匹配器`)
  assert.match(config, /respond @downloads 404/u, `${name} 未拒绝在线端下载路径`)
}

test('HTTP 与 HTTPS 部署代理均拒绝在线端安装包路径', () => {
  assertPublicDownloadsBlocked(httpConfig, 'HTTP 配置')
  assertPublicDownloadsBlocked(httpsConfig, 'HTTPS 配置')
})

test('HTTPS 更新文件只由独立更新域名目录提供', () => {
  assert.match(httpsConfig, /__UPDATE_HOST__\s*\{/u)
  assert.match(httpsConfig, /root \* "__UPDATE_ROOT__"/u)
  assert.doesNotMatch(httpConfig, /__UPDATE_ROOT__/u)
})
