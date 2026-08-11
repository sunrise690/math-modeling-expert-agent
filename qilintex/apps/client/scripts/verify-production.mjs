import { randomUUID } from 'node:crypto'
import { HocuspocusProvider } from '@hocuspocus/provider'
import * as Y from 'yjs'

const baseUrl = process.env.BASE_URL
const collabUrl = process.env.COLLAB_URL || baseUrl?.replace(/^http/, 'ws') + '/collab'
const accessCode = process.env.TEAM_ACCESS_CODE || ''

if (!baseUrl) throw new Error('请通过 BASE_URL 指定待验收的部署地址')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

async function request(path, { token, method = 'GET', body } = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: {
      ...(body ? { 'content-type': 'application/json' } : {}),
      ...(token ? { authorization: `Bearer ${token}` } : {}),
      'x-auth-realm': 'team'
    },
    body: body ? JSON.stringify(body) : undefined
  })
  const payload = await response.json().catch(() => ({}))
  return { response, payload }
}

async function login(displayName, code = accessCode) {
  const { response, payload } = await request('/auth/team', {
    method: 'POST',
    body: { displayName, accessCode: code, deviceId: randomUUID() }
  })
  assert(response.ok, `登录失败：${response.status} ${JSON.stringify(payload)}`)
  assert(payload.realm === 'team' && payload.token, '团队登录没有返回隔离的 team token')
  return payload
}

function connectDocument(projectId, token) {
  const document = new Y.Doc()
  let provider
  const ready = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('协作连接或首次同步超时')), 15_000)
    provider = new HocuspocusProvider({
      url: collabUrl,
      name: `project.${projectId}.main.tex`,
      document,
      token,
      WebSocketPolyfill: globalThis.WebSocket,
      onSynced() {
        clearTimeout(timer)
        resolve()
      },
      onAuthenticationFailed({ reason }) {
        clearTimeout(timer)
        reject(new Error(`协作认证失败：${reason}`))
      }
    })
  })
  return { document, get provider() { return provider }, ready }
}

async function waitFor(predicate, message, timeout = 10_000) {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    if (predicate()) return
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error(message)
}

async function verifyPersistence() {
  const projectId = process.env.VERIFY_PROJECT_ID
  const token = process.env.VERIFY_TOKEN
  const marker = process.env.VERIFY_MARKER
  assert(projectId && token && marker, '持久化复验缺少项目、令牌或标记')
  const connection = connectDocument(projectId, token)
  await connection.ready
  const source = connection.document.getText('content').toString()
  assert(source.includes(marker), '服务重启后没有恢复协作文档更新')
  connection.provider.destroy()
  connection.document.destroy()
  console.log(JSON.stringify({ persistence: true, projectId, marker }))
}

async function verifyFullStack() {
  assert(accessCode, '未提供 TEAM_ACCESS_CODE')

  const wrong = await request('/auth/team', {
    method: 'POST',
    body: { displayName: '错误口令测试', accessCode: `${accessCode}-wrong`, deviceId: randomUUID() }
  })
  assert(wrong.response.status === 401, `错误口令应返回401，实际为${wrong.response.status}`)

  const suffix = Date.now().toString(36)
  const owner = await login(`验收甲-${suffix}`)
  const editor = await login(`验收乙-${suffix}`)
  const outsider = await login(`验收丙-${suffix}`)
  assert(owner.token !== editor.token && editor.token !== outsider.token, '不同设备不应共享会话令牌')

  const created = await request('/api/projects', {
    token: owner.token,
    method: 'POST',
    body: { name: `云端多人验收-${suffix}` }
  })
  assert(created.response.status === 201, `创建项目失败：${JSON.stringify(created.payload)}`)
  const projectId = created.payload.project.id

  const denied = await request(`/api/projects/${projectId}/compile`, {
    token: outsider.token,
    method: 'POST',
    body: { source: '\\documentclass{article}\\begin{document}denied\\end{document}' }
  })
  assert(denied.response.status === 403, `非成员访问应返回403，实际为${denied.response.status}`)

  const invitation = await request(`/api/projects/${projectId}/invitations`, {
    token: owner.token,
    method: 'POST'
  })
  assert(invitation.response.ok && invitation.payload.token, '创建邀请失败')

  const accepted = await request(`/api/invitations/${encodeURIComponent(invitation.payload.token)}/accept`, {
    token: editor.token,
    method: 'POST'
  })
  assert(accepted.response.ok && accepted.payload.project.role === 'editor', '第二位成员接受邀请失败')

  const ownerConnection = connectDocument(projectId, owner.token)
  const editorConnection = connectDocument(projectId, editor.token)
  await Promise.all([ownerConnection.ready, editorConnection.ready])

  const marker = `% realtime-${randomUUID()}`
  const ownerText = ownerConnection.document.getText('content')
  const editorText = editorConnection.document.getText('content')
  ownerText.insert(ownerText.length, `\n${marker}\n`)
  await waitFor(() => editorText.toString().includes(marker), '第二位成员没有收到实时协作更新')
  await new Promise((resolve) => setTimeout(resolve, 2200))

  const latexSource = String.raw`\documentclass[UTF8]{ctexart}
\begin{document}
QilinTeX 云端中文编译与多人协作验收通过。
\end{document}`
  const compiled = await request(`/api/projects/${projectId}/compile`, {
    token: owner.token,
    method: 'POST',
    body: { source: latexSource }
  })
  assert(compiled.response.ok, `编译请求失败：${JSON.stringify(compiled.payload)}`)
  assert(compiled.payload.ok, `LaTeX编译失败：${compiled.payload.log}`)
  assert(compiled.payload.engine === 'latexmk', `编译器不是latexmk：${compiled.payload.engine}`)
  assert(String(compiled.payload.pdfBase64 || '').startsWith('JVBERi0'), '返回内容不是PDF')

  ownerConnection.provider.destroy()
  editorConnection.provider.destroy()
  ownerConnection.document.destroy()
  editorConnection.document.destroy()

  console.log(JSON.stringify({
    fullStack: true,
    projectId,
    marker,
    ownerToken: owner.token,
    invitationUrl: invitation.payload.url,
    compiler: compiled.payload.engine,
    pdfBytes: Buffer.from(compiled.payload.pdfBase64, 'base64').length
  }))
}

if (process.env.VERIFY_PROJECT_ID) await verifyPersistence()
else await verifyFullStack()
