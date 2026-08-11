import OpenAI from 'openai'
import { config } from './config.js'
import { askMathModelingAgent, resolveDocumentAgentMode } from './math-agent.js'
import {
  buildVisualizationInstructions, buildVisualizationTools, collectVisualizationArtifacts, planVisualization,
  type VisualizationRunSummary
} from './visualization.js'

const client = config.openai.apiKey ? new OpenAI({ apiKey: config.openai.apiKey }) : null

export async function askDocumentAgent(source: string, message: string, requestedMode = 'auto') {
  if (!message.trim()) throw new Error('问题不能为空。')
  if (message.length > 20_000) throw new Error('问题超过 20,000 字符限制。')
  if (source.length > 95_000) throw new Error('当前文档过长，请选择片段后再询问。')

  if (config.documentAgent.backend === 'math-modeling') {
    return askMathModelingAgent(source, message, requestedMode, {
      baseUrl: config.documentAgent.mathModelingUrl,
      timeoutMs: config.documentAgent.timeoutMs,
      pollIntervalMs: config.documentAgent.pollIntervalMs,
      maxArtifacts: config.openai.maxArtifacts,
      maxArtifactBytes: config.openai.maxArtifactBytes
    })
  }

  if (!client) throw new Error('OpenAI 直连助手尚未配置。请设置 OPENAI_API_KEY，或改用数模 Agent 后端。')
  const mode = resolveDocumentAgentMode(requestedMode, message)

  const capabilities = {
    codeInterpreter: config.openai.codeInterpreter,
    imageGeneration: config.openai.imageGeneration
  }
  const plan = planVisualization(message, source)
  const tools = buildVisualizationTools(plan, capabilities)

  const response = await client.responses.create({
    model: config.openai.model,
    instructions: [
      '你是数学建模 LaTeX 协作编辑器中的文档与证据可视化助手。使用简体中文，基于用户提供的当前 main.tex 回答。保持技术准确；若给出 LaTeX，使用可复制的代码块；不要声称已经修改文档。',
      '把绘图视为证据链的一部分：problem -> model -> computation -> evidence -> conclusion。图形必须服务于明确结论，不能只做装饰。',
      buildVisualizationInstructions(plan, capabilities)
    ].join('\n\n'),
    input: `用户要求：\n${message}\n\n当前 main.tex：\n\n${source}`,
    ...(tools.length ? {
      tools,
      tool_choice: plan.forceTool ? 'required' as const : 'auto' as const,
      include: ['code_interpreter_call.outputs' as const]
    } : {})
  })

  const collected = await collectVisualizationArtifacts(response, client, {
    maxArtifacts: config.openai.maxArtifacts,
    maxArtifactBytes: config.openai.maxArtifactBytes
  })
  const visualization: VisualizationRunSummary = {
    intent: plan.intent,
    phase: plan.phase,
    requestedTools: plan.preferredTools,
    usedTools: collected.usedTools,
    rationale: plan.rationale,
    warnings: collected.warnings
  }
  return { text: response.output_text, artifacts: collected.artifacts, visualization, backend: 'openai' as const, mode }
}
