import { useMemo, useState } from 'react'
import {
  ArrowRight, BookOpenText, Check, CircleCheckBig, Clipboard, FileCode2,
  GitBranch, LockKeyhole, PanelRight, TerminalSquare
} from 'lucide-react'
import type { Project } from '../lib/types'

interface Props {
  project: Project
  onOpenEditor: () => void
  onCopyCommand: (command: string, label: string) => void
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

const evidenceChain = ['赛题', '模型', '计算', '证据', '结论']

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

export function ModelingDashboard({ project, onOpenEditor, onCopyCommand }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(1)
  const selected = stages[selectedIndex]
  const commandText = useMemo(() => `$cumcm-modeling ${selected.command} 当前项目“${project.name}”`, [project.name, selected.command])

  return (
    <div className="modeling-dashboard">
      <header className="modeling-summary">
        <div><h1>{project.name}</h1><p>数模流程</p></div>
        <div className="workflow-source"><span>状态</span><strong>未连接</strong></div>
      </header>

      <nav className="stage-tabs" aria-label="数学建模阶段">
        {stages.map((stage, index) => (
          <button
            key={stage.command}
            className={selectedIndex === index ? 'active' : index === 0 ? 'established' : ''}
            onClick={() => setSelectedIndex(index)}
            aria-current={selectedIndex === index ? 'step' : undefined}
          >
            <span>{index === 0 ? <Check size={13} /> : String(index + 1).padStart(2, '0')}</span>
            <div><strong>{stage.shortTitle}</strong><small>{stageState(index)}</small></div>
            {index > 1 && <LockKeyhole size={13} />}
          </button>
        ))}
      </nav>

      <div className="modeling-content">
        <main className="mission-panel">
          <article className="task-thread">
            <header className="task-heading">
              <span className="task-index">{String(selectedIndex + 1).padStart(2, '0')}</span>
              <div><span className="task-state">{stageState(selectedIndex)}</span><h2>{selected.title}</h2><p>{selected.purpose}</p></div>
            </header>

            <section className="command-launch">
              <div><span>命令</span><code>{commandText}</code></div>
              <button onClick={() => onCopyCommand(selected.command, selected.shortTitle)}><Clipboard size={16} />复制</button>
            </section>

            <section className="gate-panel">
              <CircleCheckBig size={21} />
              <div><h3>完成条件</h3><p>{selected.gate}</p></div>
            </section>
          </article>

          <section className="deliverables-panel">
            <header><h2>交付物</h2><p>通过后生成</p></header>
            <div className="artifact-list">
              {selected.artifacts.map((artifact) => (
                <div key={artifact}><FileCode2 size={16} /><code>{artifact}</code><span>待生成</span></div>
              ))}
            </div>
          </section>
        </main>

        <aside className="evidence-console">
          <header><PanelRight size={18} /><div><h2>证据链</h2><p>赛题 → 结论</p></div></header>
          <ol className="evidence-flow">
            {evidenceChain.map((item, index) => (
              <li key={item} className={selected.evidenceIndex === index ? 'focused' : ''}>
                <span>{String(index + 1).padStart(2, '0')}</span><strong>{item}</strong><small>{selected.evidenceIndex === index ? '当前' : '待同步'}</small>
              </li>
            ))}
          </ol>
          <div className="state-source"><strong>数据源</strong><p><code>workflow_state.json</code> 未连接，不推测进度。</p></div>
          <div className="project-facts"><span>{project.name}</span><p>{project.role === 'owner' ? '项目所有者' : project.role === 'editor' ? '可编辑成员' : '只读成员'} · {formatUpdatedAt(project.updatedAt)}</p></div>
          <button className="open-paper" onClick={onOpenEditor}><BookOpenText size={16} />打开论文<ArrowRight size={15} /></button>
        </aside>
      </div>

      <footer className="modeling-actions">
        <button onClick={() => onCopyCommand('status', '状态检查')}><TerminalSquare size={15} />状态</button>
        <button onClick={() => onCopyCommand('end-to-end', '完整流程')}><GitBranch size={15} />运行全流程</button>
      </footer>
    </div>
  )
}
