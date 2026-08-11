import { describe, expect, it, vi } from 'vitest'
import {
  buildVisualizationInstructions, buildVisualizationTools, collectVisualizationArtifacts, planVisualization
} from './visualization.js'

describe('绘图能力路由', () => {
  it('普通文档请求不会被 main.tex 中已有图表误触发', () => {
    const plan = planVisualization('请润色引言第二段', '\\begin{figure}数据热力图\\end{figure}')
    expect(plan).toMatchObject({ intent: 'none', needsCodeInterpreter: false, needsImageGeneration: false, forceTool: false })
  })

  it('探索性统计图只开放代码绘图，并优先 Seaborn/Plotly', () => {
    const plan = planVisualization('请绘制 EDA 分布图，看看异常值')
    expect(plan).toMatchObject({
      intent: 'data_plot', phase: 'exploration', needsCodeInterpreter: true, needsImageGeneration: false, forceTool: true
    })
    expect(plan.preferredTools).toEqual(['seaborn', 'plotly'])
  })

  it('论文正式图优先 Matplotlib，禁止把 image generation 当作统计绘图器', () => {
    const plan = planVisualization('生成论文正式的模型残差图和 95% 置信区间')
    expect(plan).toMatchObject({ intent: 'data_plot', phase: 'validation', needsCodeInterpreter: true, needsImageGeneration: false })
    expect(plan.preferredTools).toContain('matplotlib')
    const instructions = buildVisualizationInstructions(plan, { codeInterpreter: true, imageGeneration: true })
    expect(instructions).toContain('严禁用它生成统计图')
  })

  it('结构图走确定性工具，封面插画才走生成式图片', () => {
    const diagram = planVisualization('请绘制模型技术路线流程图')
    expect(diagram).toMatchObject({ intent: 'diagram', needsCodeInterpreter: true, needsImageGeneration: false })
    expect(diagram.preferredTools).toEqual(['graphviz', 'networkx', 'tikz'])

    const cover = planVisualization('请直接生图，做一张数学建模论文封面插画')
    expect(cover).toMatchObject({ intent: 'generative_image', needsCodeInterpreter: false, needsImageGeneration: true, forceTool: true })
  })

  it('能力开关会从 API 请求中移除对应工具', () => {
    const plan = planVisualization('请直接生图，生成一张封面插画')
    expect(buildVisualizationTools(plan, { codeInterpreter: true, imageGeneration: false })).toEqual([])
    expect(buildVisualizationTools(plan, { codeInterpreter: true, imageGeneration: true })).toMatchObject([{ type: 'image_generation' }])
  })
})

describe('绘图产物收集', () => {
  it('合并 image generation 与代码绘图文件，并过滤非图形文件', async () => {
    const list = vi.fn().mockResolvedValue({
      data: [
        { id: 'png-file', bytes: 3, path: '/mnt/data/residual_plot.png' },
        { id: 'csv-file', bytes: 3, path: '/mnt/data/source.csv' }
      ]
    })
    const retrieve = vi.fn().mockResolvedValue(new Response(new Uint8Array([1, 2, 3])))
    const fakeClient = { containers: { files: { list, content: { retrieve } } } }
    const response = {
      output: [
        { type: 'image_generation_call' as const, id: 'image-call-12345678', result: Buffer.from('image').toString('base64'), status: 'completed' as const },
        { type: 'code_interpreter_call' as const, id: 'code-call', code: 'pass', container_id: 'container-1', outputs: [], status: 'completed' as const }
      ]
    }

    const result = await collectVisualizationArtifacts(response, fakeClient, { maxArtifacts: 4, maxArtifactBytes: 1024 })

    expect(result.usedTools).toEqual(['image_generation', 'code_interpreter'])
    expect(result.artifacts).toHaveLength(2)
    expect(result.artifacts.map((item) => item.sourceTool)).toEqual(['image_generation', 'code_interpreter'])
    expect(result.artifacts[1]).toMatchObject({ name: 'residual_plot.png', mimeType: 'image/png', kind: 'data_figure' })
    expect(retrieve).toHaveBeenCalledOnce()
  })

  it('单个产物过大时只给警告，不让整个 Agent 请求失败', async () => {
    const fakeClient = {
      containers: { files: {
        list: vi.fn().mockResolvedValue({ data: [{ id: 'large', bytes: 2048, path: '/mnt/data/large.pdf' }] }),
        content: { retrieve: vi.fn() }
      } }
    }
    const response = {
      output: [{ type: 'code_interpreter_call' as const, id: 'code-call', code: 'pass', container_id: 'container-1', outputs: [], status: 'completed' as const }]
    }

    const result = await collectVisualizationArtifacts(response, fakeClient, { maxArtifacts: 4, maxArtifactBytes: 1024 })
    expect(result.artifacts).toEqual([])
    expect(result.warnings[0]).toContain('超过单文件大小限制')
  })
})
