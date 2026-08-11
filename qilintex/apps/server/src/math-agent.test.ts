import { describe, expect, it, vi } from 'vitest'
import { askMathModelingAgent, normalizeMathAgentBaseUrl, resolveDocumentAgentMode } from './math-agent.js'

describe('数模 Agent 模式路由', () => {
  it('按请求语义选择建模、交付、论文和质检模式', () => {
    expect(resolveDocumentAgentMode('auto', '请比较优化算法并建立模型')).toBe('solver')
    expect(resolveDocumentAgentMode('auto', '请完成整题并交付论文')).toBe('cumcm')
    expect(resolveDocumentAgentMode('auto', '请润色摘要')).toBe('paper')
    expect(resolveDocumentAgentMode('auto', '请严格审稿并检查风险')).toBe('reviewer')
    expect(resolveDocumentAgentMode('paper', '请建立模型')).toBe('paper')
  })

  it('只允许连接本机回环地址', () => {
    expect(normalizeMathAgentBaseUrl('http://127.0.0.1:8765/')).toBe('http://127.0.0.1:8765')
    expect(() => normalizeMathAgentBaseUrl('https://example.com')).toThrow('本机回环地址')
    expect(() => normalizeMathAgentBaseUrl('http://user:pass@127.0.0.1:8765')).toThrow('不能包含凭据')
  })
})

describe('数模 Agent 服务端桥接', () => {
  it('提交任务、轮询完成并回传质量评分与产物', async () => {
    const runId = 'a'.repeat(32)
    let submittedBody: Record<string, unknown> = {}
    const fetchImpl = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/api/runs') && init?.method === 'POST') {
        submittedBody = JSON.parse(String(init.body))
        return Response.json({ run: { id: runId, status: 'queued' } }, { status: 202 })
      }
      if (url.endsWith(`/api/runs/${runId}`)) {
        return Response.json({
          run: { id: runId, status: 'completed', output: '完成建模分析。', quality: { total: 91, threshold: 82, passed: true, grade: 'A' } }
        })
      }
      if (url.endsWith(`/api/runs/${runId}/artifacts`)) {
        return Response.json({ artifacts: [{ name: 'result.svg', url: `/api/artifacts/${runId}/result.svg`, mimeType: 'image/svg+xml' }] })
      }
      if (url.endsWith(`/api/artifacts/${runId}/result.svg`)) {
        return new Response('<svg/>', { headers: { 'Content-Type': 'image/svg+xml', 'Content-Length': '6' } })
      }
      return new Response('not found', { status: 404 })
    }) as typeof fetch

    const result = await askMathModelingAgent('\\section{模型}', '请审核模型并检查风险', 'auto', {
      baseUrl: 'http://127.0.0.1:8765',
      timeoutMs: 10_000,
      pollIntervalMs: 1,
      maxArtifacts: 4,
      maxArtifactBytes: 1024,
      fetchImpl
    })

    expect(submittedBody).toMatchObject({ mode: 'reviewer', language: '简体中文', requirements: ['风险检查'] })
    expect(String(submittedBody.content)).toContain('<qilintex_main_tex>')
    expect(result).toMatchObject({
      backend: 'math_modeling_agent', mode: 'reviewer', runId, text: '完成建模分析。', quality: { total: 91, passed: true }
    })
    expect(result.artifacts).toHaveLength(1)
    expect(result.artifacts[0]).toMatchObject({ name: 'result.svg', kind: 'modeling_artifact', sourceTool: 'math_modeling_agent' })
    expect(result.visualization.usedTools).toEqual(['math_modeling_agent'])
  })

  it('拒绝数模 Agent 返回的跨源产物地址', async () => {
    const runId = 'b'.repeat(32)
    const fetchImpl = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/api/runs') && init?.method === 'POST') return Response.json({ run: { id: runId, status: 'completed', output: 'ok' } })
      if (url.endsWith(`/api/runs/${runId}/artifacts`)) {
        return Response.json({ artifacts: [{ name: 'unsafe.svg', url: 'https://example.com/unsafe.svg', mimeType: 'image/svg+xml' }] })
      }
      return new Response('not found', { status: 404 })
    }) as typeof fetch

    const result = await askMathModelingAgent('正文', '请润色', 'paper', {
      baseUrl: 'http://localhost:8765', timeoutMs: 10_000, pollIntervalMs: 1,
      maxArtifacts: 4, maxArtifactBytes: 1024, fetchImpl
    })
    expect(result.artifacts).toEqual([])
    expect(result.visualization.warnings[0]).toContain('产物地址无效')
  })
})
