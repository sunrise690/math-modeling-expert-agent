import { execFile } from 'node:child_process'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, join } from 'node:path'
import { promisify } from 'node:util'
import { config } from './config.js'

const run = promisify(execFile)

export async function compileLatex(source: string) {
  if (!source.trim()) return { ok: false, log: 'main.tex 为空。' }
  if (Buffer.byteLength(source, 'utf8') > 1_000_000) return { ok: false, log: 'main.tex 超过 1 MB 限制。' }

  const directory = await mkdtemp(join(tmpdir(), 'tonggao-tex-'))
  const sourcePath = join(directory, 'main.tex')
  const executable = config.tex.path || config.tex.engine
  const engineName = basename(executable).toLowerCase()
  const isLatexmk = engineName.includes('latexmk')
  const args = isLatexmk
    ? [config.tex.latexmkEngine === 'xelatex' ? '-xelatex' : '-pdf', '-interaction=nonstopmode', '-halt-on-error', `-outdir=${directory}`, sourcePath]
    : [sourcePath, '--outdir', directory, '--keep-logs']

  try {
    await writeFile(sourcePath, source, 'utf8')
    const { stdout, stderr } = await run(executable, args, { cwd: directory, timeout: 30_000, maxBuffer: 2_000_000, windowsHide: true })
    const pdf = await readFile(join(directory, 'main.pdf'))
    return { ok: true, pdfBase64: pdf.toString('base64'), log: `${stdout}\n${stderr}`.trim(), engine: isLatexmk ? 'latexmk' : 'tectonic' }
  } catch (error) {
    const issue = error as NodeJS.ErrnoException & { stdout?: string; stderr?: string; killed?: boolean }
    const unavailable = issue.code === 'ENOENT'
    const log = unavailable
      ? `未找到 LaTeX 编译器“${executable}”。请安装 Tectonic，或在 .env 中设置 TEX_ENGINE_PATH。`
      : issue.killed ? '编译超过 30 秒，已终止。' : `${issue.stderr || ''}\n${issue.stdout || ''}\n${issue.message}`.trim()
    return { ok: false, log, engine: isLatexmk ? 'latexmk' : 'tectonic' }
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
}
