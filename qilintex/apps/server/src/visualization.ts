import { basename, extname } from 'node:path'
import type OpenAI from 'openai'
import type { Response as OpenAIResponse, Tool } from 'openai/resources/responses/responses'

export type VisualizationIntent = 'none' | 'data_plot' | 'diagram' | 'generative_image' | 'hybrid'
export type VisualizationPhase = 'none' | 'exploration' | 'analysis' | 'validation' | 'publication' | 'presentation'
export type VisualizationTool = 'matplotlib' | 'seaborn' | 'plotly' | 'graphviz' | 'networkx' | 'tikz' | 'image_generation'

export interface VisualizationCapabilities {
  codeInterpreter: boolean
  imageGeneration: boolean
}

export interface VisualizationPlan {
  intent: VisualizationIntent
  phase: VisualizationPhase
  forceTool: boolean
  needsCodeInterpreter: boolean
  needsImageGeneration: boolean
  preferredTools: VisualizationTool[]
  rationale: string
}

export interface AgentArtifact {
  id: string
  name: string
  mimeType: string
  base64: string
  kind: 'data_figure' | 'generated_image' | 'modeling_artifact'
  sourceTool: 'code_interpreter' | 'image_generation' | 'math_modeling_agent'
}

export interface VisualizationRunSummary {
  intent: VisualizationIntent
  phase: VisualizationPhase
  requestedTools: VisualizationTool[]
  usedTools: Array<'code_interpreter' | 'image_generation' | 'math_modeling_agent'>
  rationale: string
  warnings: string[]
}

const DATA_TERMS = [
  '数据', '统计', '回归', '残差', '误差', '置信区间', '分布', '变量', '曲线', '柱状图', '条形图', '折线图',
  '箱线图', '小提琴图', '散点图', '热力图', '等高线', '雷达图', '地图', '网络图', '甘特图', '帕累托',
  '灵敏度', '敏感性', '拟合', 'roc', '混淆矩阵', '模型结果', 'matplotlib', 'seaborn', 'plotly',
  'plot', 'chart', 'figure', 'visualization'
]
const DIAGRAM_TERMS = [
  '流程图', '框架图', '架构图', '机制图', '技术路线', '示意图', '概念图', '拓扑图', '因果图', '决策树',
  'mermaid', 'tikz', 'pgfplots', 'graphviz', 'drawio', 'diagram'
]
const IMAGE_TERMS = [
  '插画', '封面图', '海报', '背景图', '氛围图', '艺术风格', '写实图', '照片感', '渲染图', '直接生图',
  'image generation', 'imagegen', '生成式图片'
]
const GENERAL_VISUAL_TERMS = ['画图', '绘图', '可视化', '图表', '图像', '配图']

function containsAny(text: string, terms: string[]) {
  return terms.some((term) => text.includes(term))
}

function inferPhase(text: string): VisualizationPhase {
  if (/探索|初步|eda|看(?:看)?分布|数据概览|筛选变量/i.test(text)) return 'exploration'
  if (/验证|诊断|残差|敏感性|灵敏度|稳健|误差分析|消融/i.test(text)) return 'validation'
  if (/论文|正式图|终稿|投稿|发表|图注|出版|高质量/i.test(text)) return 'publication'
  if (/答辩|汇报|演示|ppt|幻灯片/i.test(text)) return 'presentation'
  return 'analysis'
}

function requestsRenderedArtifact(text: string) {
  return /直接生图|画图|画一张|画出|绘制|渲染|制作.{0,8}(图|figure|chart)|生成.{0,12}(图|figure|chart|image)|输出.{0,8}(图|figure|chart)|(?:create|render|generate).{0,12}(?:plot|chart|figure|image)/i.test(text)
}

export function planVisualization(message: string, source = ''): VisualizationPlan {
  // 是否调用昂贵绘图工具只由本轮请求决定，避免 main.tex 中已有的“图/数据”误触发工具。
  void source
  const text = message.toLowerCase()
  const hasData = containsAny(text, DATA_TERMS)
  const hasDiagram = containsAny(text, DIAGRAM_TERMS)
  const hasImage = containsAny(text, IMAGE_TERMS)
  const hasVisual = hasData || hasDiagram || hasImage || containsAny(text, GENERAL_VISUAL_TERMS)

  if (!hasVisual) {
    return {
      intent: 'none', phase: 'none', forceTool: false, needsCodeInterpreter: false, needsImageGeneration: false,
      preferredTools: [], rationale: '当前请求不需要绘图工具。'
    }
  }

  let intent: VisualizationIntent
  if (hasImage && (hasData || hasDiagram)) intent = 'hybrid'
  else if (hasImage) intent = 'generative_image'
  else if (hasDiagram && !hasData) intent = 'diagram'
  else intent = 'data_plot'

  const phase = inferPhase(text)
  const preferredTools: VisualizationTool[] = []
  if (intent === 'data_plot' || intent === 'hybrid') {
    if (phase === 'exploration') preferredTools.push('seaborn', 'plotly')
    else preferredTools.push('matplotlib', 'seaborn')
  }
  if (intent === 'diagram' || (intent === 'hybrid' && hasDiagram)) preferredTools.push('graphviz', 'networkx', 'tikz')
  if (intent === 'generative_image' || intent === 'hybrid') preferredTools.push('image_generation')

  const rationale = intent === 'generative_image'
    ? '请求面向非定量视觉素材，可使用生成式图片。'
    : intent === 'diagram'
      ? '请求面向结构关系，优先使用可复现的结构图工具。'
      : intent === 'hybrid'
        ? '请求同时包含可复现图形与生成式视觉，必须分开产出并标明用途。'
        : '请求包含数据或模型证据，必须使用可复现的代码绘图。'

  return {
    intent,
    phase,
    forceTool: requestsRenderedArtifact(message.toLowerCase()),
    needsCodeInterpreter: intent === 'data_plot' || intent === 'diagram' || intent === 'hybrid',
    needsImageGeneration: intent === 'generative_image' || intent === 'hybrid',
    preferredTools: [...new Set(preferredTools)],
    rationale
  }
}

export function buildVisualizationTools(plan: VisualizationPlan, capabilities: VisualizationCapabilities): Tool[] {
  const tools: Tool[] = []
  if (plan.needsCodeInterpreter && capabilities.codeInterpreter) {
    tools.push({ type: 'code_interpreter', container: { type: 'auto' } })
  }
  if (plan.needsImageGeneration && capabilities.imageGeneration) {
    tools.push({
      type: 'image_generation', model: 'gpt-image-1', output_format: 'png', background: 'auto',
      moderation: 'auto', partial_images: 0
    })
  }
  return tools
}

export function buildVisualizationInstructions(plan: VisualizationPlan, capabilities: VisualizationCapabilities) {
  if (plan.intent === 'none') {
    return '当前请求没有绘图意图。不要为了装饰而调用绘图或图像生成工具。'
  }

  const availability = [
    capabilities.codeInterpreter ? '代码绘图可用' : '代码绘图已禁用',
    capabilities.imageGeneration ? '生成式图片可用' : '生成式图片已禁用'
  ].join('；')

  return `
当前绘图路由：${plan.intent}；工作阶段：${plan.phase}；建议工具：${plan.preferredTools.join('、') || '无'}。${availability}。

严格按以下顺序协作：
1. 先确定这张图要支持的结论、数据来源、变量含义、单位和输出媒介；信息不足时明确缺口，不得编造数据。
2. 探索阶段优先 Seaborn 或 Plotly 查看分布、异常值和交互关系；模型结果稳定后，再用 Matplotlib/Seaborn 生成论文正式图。Plotly 主要用于交互探索，不把交互 HTML 当作论文终稿。
3. 多面板、精确排版和矢量导出优先 Matplotlib；统计分布与分组比较优先 Seaborn；流程、网络和拓扑优先 Graphviz/NetworkX；适合直接嵌入 LaTeX 的小型公式图可返回 TikZ/PGFPlots 代码。
4. image_generation 只允许用于封面、插画、氛围素材或不承载定量证据的概念视觉。严禁用它生成统计图、拟合曲线、坐标数据、精确流程结构、虚构实验结果或替代真实照片证据。
5. 执行代码绘图时，保留可复现代码，并将正式图保存为 PNG，同时尽量保存 SVG 或 PDF；文件名使用英文、数字、下划线。中文字体不可用时应主动选择可用字体并避免乱码。
6. 生成后必须复核：坐标与单位、图例、色盲友好配色、字号、样本量/误差定义、图注、数据来源和是否真正支持目标结论。柱状图原则上从零开始，禁止 rainbow/jet 色图和无意义 3D 效果。
7. 最终回复说明实际使用的工具、图的证据用途、仍缺少的信息以及建议插入 LaTeX 的位置；不要声称已经自动修改 main.tex。
`.trim()
}

const MIME_TYPES: Record<string, string> = {
  '.png': 'image/png', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.pdf': 'application/pdf'
}

interface ContainerFile {
  id: string
  bytes: number
  path: string
}

interface ArtifactClient {
  containers: {
    files: {
      list(containerId: string, params?: { order?: 'asc' | 'desc' }): Promise<{ data: ContainerFile[] }>
      content: { retrieve(fileId: string, params: { container_id: string }): Promise<Response> }
    }
  }
}

function safeArtifactName(path: string, fallback: string) {
  const raw = basename(path).replace(/[^a-zA-Z0-9._-]/g, '_')
  return raw || fallback
}

function uniqueName(name: string, used: Set<string>) {
  if (!used.has(name)) {
    used.add(name)
    return name
  }
  const extension = extname(name)
  const stem = name.slice(0, name.length - extension.length)
  let index = 2
  while (used.has(`${stem}_${index}${extension}`)) index += 1
  const result = `${stem}_${index}${extension}`
  used.add(result)
  return result
}

export async function collectVisualizationArtifacts(
  response: Pick<OpenAIResponse, 'output'>,
  apiClient: OpenAI | ArtifactClient,
  limits: { maxArtifacts: number; maxArtifactBytes: number }
) {
  const artifacts: AgentArtifact[] = []
  const warnings: string[] = []
  const usedTools = new Set<'code_interpreter' | 'image_generation'>()
  const usedNames = new Set<string>()

  for (const item of response.output) {
    if (item.type !== 'image_generation_call') continue
    usedTools.add('image_generation')
    if (!item.result || artifacts.length >= limits.maxArtifacts) continue
    const bytes = Buffer.byteLength(item.result, 'base64')
    if (bytes > limits.maxArtifactBytes) {
      warnings.push(`生成式图片超过 ${limits.maxArtifactBytes} 字节限制，未随回复返回。`)
      continue
    }
    artifacts.push({
      id: item.id,
      name: uniqueName(`generated_${item.id.slice(-8)}.png`, usedNames),
      mimeType: 'image/png',
      base64: item.result,
      kind: 'generated_image',
      sourceTool: 'image_generation'
    })
  }

  const containerIds = new Set(response.output
    .filter((item) => item.type === 'code_interpreter_call')
    .map((item) => {
      usedTools.add('code_interpreter')
      return item.container_id
    }))

  for (const containerId of containerIds) {
    if (artifacts.length >= limits.maxArtifacts) break
    try {
      const page = await apiClient.containers.files.list(containerId, { order: 'asc' })
      for (const file of page.data) {
        if (artifacts.length >= limits.maxArtifacts) break
        const extension = extname(file.path).toLowerCase()
        const mimeType = MIME_TYPES[extension]
        if (!mimeType) continue
        if (file.bytes > limits.maxArtifactBytes) {
          warnings.push(`${basename(file.path)} 超过单文件大小限制，未随回复返回。`)
          continue
        }
        const content = await apiClient.containers.files.content.retrieve(file.id, { container_id: containerId })
        const bytes = Buffer.from(await content.arrayBuffer())
        artifacts.push({
          id: file.id,
          name: uniqueName(safeArtifactName(file.path, `figure_${file.id}${extension}`), usedNames),
          mimeType,
          base64: bytes.toString('base64'),
          kind: 'data_figure',
          sourceTool: 'code_interpreter'
        })
      }
    } catch (error) {
      warnings.push(`绘图已完成，但读取代码绘图产物失败：${(error as Error).message}`)
    }
  }

  if (artifacts.length >= limits.maxArtifacts) warnings.push(`绘图产物最多返回 ${limits.maxArtifacts} 个。`)
  return { artifacts, warnings, usedTools: [...usedTools] }
}
