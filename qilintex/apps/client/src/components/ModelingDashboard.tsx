import { useMemo, useState } from 'react'
import {
  ArrowRight, BookOpenText, Bot, Check, ChevronDown, CircleAlert, CircleCheckBig, Download, FileCode2,
  GitBranch, LoaderCircle, TerminalSquare, X
} from 'lucide-react'
import type { AgentResult, Project } from '../lib/types'

interface Props {
  project: Project
  onOpenEditor: () => void
  onRunAgent: (command: string, label: string) => Promise<AgentResult>
}

interface StageDefinition {
  command: string
  title: string
  shortTitle: string
  purpose: string
  gate: string
  artifacts: string[]
  evidenceIndex: number
}

const stages: StageDefinition[] = [
  { command: 'init', title: '建立项目', shortTitle: '初始化', purpose: '定位赛题、附件、规则与交付要求。', gate: '输入完整，缺失项已记录。', artifacts: ['data/raw/', '项目元数据', '比赛与交付约束'], evidenceIndex: 0 },
  { command: 'analyze', title: '拆解赛题', shortTitle: '赛题解析', purpose: '明确每问的目标、变量、约束、数据与评价指标。', gate: '每个子问题都有可执行定义。', artifacts: ['references/problem_decomposition.md', 'references/problem_structure.json', 'references/data_dictionary.md'], evidenceIndex: 0 },
  { command: 'route', title: '选择模型路线', shortTitle: '路线选择', purpose: '比较候选模型、基线与验证方案。', gate: '主路线有数据依据和可执行验证。', artifacts: ['references/model_route_candidates.json', 'references/model_selection.md', 'references/innovation_plan.md'], evidenceIndex: 1 },
  { command: 'solve', title: '求解与验证', shortTitle: '模型求解', purpose: '运行可复现计算，检查误差、可行性与稳健性。', gate: '结果可复现，限制已记录。', artifacts: ['src/run_all.py', 'reports/summary.json', 'reports/summary_normalized.json'], evidenceIndex: 2 },
  { command: 'visualize', title: '生成证据图表', shortTitle: '证据图表', purpose: '让每张正式图对应一个结论或验证。', gate: '图表包含来源、坐标、单位与图注。', artifacts: ['references/figure_plan.md', 'figures/figure_manifest.json', 'figures/'], evidenceIndex: 3 },
  { command: 'write', title: '撰写论文', shortTitle: '论文写作', purpose: '用模型、验证与图表组织正式论文。', gate: '结论和摘要数字均可回溯。', artifacts: ['paper/main.tex', 'paper/main.pdf', 'references/claim_evidence_map.md'], evidenceIndex: 4 },
  { command: 'audit', title: '审查风险', shortTitle: '风险审查', purpose: '检查漏问、错配、泄漏、证据缺口与表述边界。', gate: '问题已归类并形成修复清单。', artifacts: ['reports/artifact_contract_report.json', 'reports/redteam_review.md', 'reports/verification_report.md'], evidenceIndex: 3 },
  { command: 'polish', title: '确认交付', shortTitle: '最终收尾', purpose: '修复阻塞项，重建结果并检查最终 PDF。', gate: '结果可复现，核心结论有证据。', artifacts: ['validation/latest_score.md', 'reports/workflow_state.json', '最终 PDF 与支持材料'], evidenceIndex: 4 },
]

function formatUpdatedAt(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '更新时间未知'
  return `更新于 ${new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date)}`
}

function stageState(index: number) {
  if (index === 0) return '完成'
  if (index === 1) return '下一步'
  return '待前序'
}

export function ModelingDashboard({ project, onOpenEditor, onRunAgent }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(1)
  const [showStages, setShowStages] = useState(false)
  const [running, setRunning] = useState('')
  const [runResult, setRunResult] = useState<AgentResult | null>(null)
  const [runError, setRunError] = useState('')
  const selected = stages[selectedIndex]
  const commandText = useMemo(() => `$cumcm-modeling ${selected.command} 当前项目“${project.name}”`, [project.name, selected.command])

  const run = async (command: string, label: string) => {
    if (running) return
    setRunning(label)
    setRunResult(null)
    setRunError('')
    try {
      setRunResult(await onRunAgent(command, label))
    } catch (error) {
      setRunError(error instanceof Error ? error.message : 'Agent 执行失败。')
    } finally {
      setRunning('')
    }
  }

  return (
    <div className="modeling-dashboard">
      <header className="modeling-simple-head">
        <div><p className="eyebrow">数模 Agent</p><h1>{project.name}</h1><span>{formatUpdatedAt(project.updatedAt)}</span></div>
        <button className="run-all-button" onClick={() => { void run('end-to-end', '完整流程') }} disabled={Boolean(running)}>{running === '完整流程' ? <LoaderCircle className="spin" size={15} /> : <GitBranch size={15} />}运行完整流程</button>
      </header>

      <div className="workflow-picker-wrap">
        <button className="workflow-picker" type="button" aria-expanded={showStages} onClick={() => setShowStages((value) => !value)}>
          <span className="workflow-number">{String(selectedIndex + 1).padStart(2, '0')}</span>
          <span><small>当前任务</small><strong>{selected.shortTitle}</strong></span>
          <ChevronDown size={16} />
        </button>
        {showStages && <div className="workflow-menu" role="menu">
          {stages.map((stage, index) => <button type="button" role="menuitem" key={stage.command} className={selectedIndex === index ? 'active' : ''} onClick={() => { setSelectedIndex(index); setShowStages(false) }}>
            <span>{index === 0 ? <Check size={13} /> : String(index + 1).padStart(2, '0')}</span>
            <div><strong>{stage.shortTitle}</strong><small>{stage.purpose}</small></div>
            {selectedIndex === index && <Check size={14} />}
          </button>)}
        </div>}
      </div>

      <main className="modeling-focus modeling-focus-simple">
        <section className="focus-task">
          <span className="task-state">{stageState(selectedIndex)}</span>
          <h2>{selected.title}</h2>
          <p>{selected.purpose}</p>
          <div className="modeling-essential"><CircleCheckBig size={16} /><span><small>完成条件</small><strong>{selected.gate}</strong></span></div>
          <button className="focus-run" onClick={() => { void run(selected.command, selected.shortTitle) }} disabled={Boolean(running)}>{running === selected.shortTitle ? <LoaderCircle className="spin" size={17} /> : <Bot size={17} />}<span>{running === selected.shortTitle ? 'Agent 正在执行' : '交给 Agent'}</span><ArrowRight size={15} /></button>
          <details className="modeling-more">
            <summary>更多详情</summary>
            <div className="focus-command"><span>执行命令</span><code>{commandText}</code></div>
            <div className="modeling-more-artifacts"><span>本步交付</span>{selected.artifacts.map((artifact) => <code key={artifact}>{artifact}</code>)}</div>
            <div className="focus-links">
              <button onClick={() => { void run('status', '状态检查') }} disabled={Boolean(running)}>{running === '状态检查' ? <LoaderCircle className="spin" size={15} /> : <TerminalSquare size={15} />}检查状态</button>
              <button onClick={onOpenEditor}><BookOpenText size={15} />打开论文</button>
            </div>
          </details>
        </section>
      </main>
      {(running || runResult || runError) && <section className="modeling-run-output" aria-live="polite">
        <header>
          <div>{running ? <LoaderCircle className="spin" size={17} /> : runError ? <CircleAlert size={17} /> : <CircleCheckBig size={17} />}<span><strong>{running ? `正在执行${running}` : runError ? 'Agent 执行失败' : 'Agent 已完成'}</strong><small>{running ? '任务已直接提交，完成后结果会显示在这里。' : runResult ? `${runResult.mode} · ${runResult.backend === 'math_modeling_agent' ? '数模 Agent' : 'OpenAI'}` : runError}</small></span></div>
          {!running && <button type="button" className="icon-button" onClick={() => { setRunResult(null); setRunError('') }} aria-label="关闭运行结果"><X size={16} /></button>}
        </header>
        {runResult?.text && <pre>{runResult.text}</pre>}
        {runResult && runResult.artifacts.length > 0 && <div className="modeling-run-artifacts">{runResult.artifacts.map((artifact) => <a key={artifact.id} href={`data:${artifact.mimeType};base64,${artifact.base64}`} download={artifact.name}><FileCode2 size={15} /><span>{artifact.name}</span><Download size={14} /></a>)}</div>}
      </section>}
    </div>
  )
}
