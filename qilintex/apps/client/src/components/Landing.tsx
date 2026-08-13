import { ChevronRight, Download, Monitor } from 'lucide-react'

const SETUP_URL = 'https://updates.qilintex.top/Qilintex-Setup-0.1.1-x64.exe'
const PORTABLE_URL = 'https://updates.qilintex.top/Qilintex-Portable-0.1.1-x64.exe'

interface Props {
  onUseOnline: () => void
}

export function Landing({ onUseOnline }: Props) {
  return (
    <main className="product-entry">
      <div className="entry-welcome">
        <section className="entry-hero">
          <img src="./app-icon.jpg" alt="" />
          <div><h1>Qilintex</h1><p>数模 Agent 与 QilinTeX 协作工作台</p></div>
        </section>

        <section className="entry-paths" aria-label="使用方式">
          <article>
            <span className="entry-path-index">01</span>
            <Monitor size={25} />
            <div><h2>在线使用</h2><p>打开项目、编辑 LaTeX、编译 PDF，并与团队成员实时协作。</p></div>
            <button type="button" onClick={onUseOnline}>进入在线工作台 <ChevronRight size={18} /></button>
          </article>
          <article>
            <span className="entry-path-index">02</span>
            <Download size={25} />
            <div><h2>下载应用</h2><p>在当前电脑运行数模 Agent、登录 Codex，并接收后续版本更新。</p></div>
            <a className="entry-download-primary" href={SETUP_URL}>下载安装版 <Download size={18} /></a>
            <a className="entry-portable" href={PORTABLE_URL}>下载便携版</a>
          </article>
        </section>

        <section className="entry-details">
          <div><strong>本机运行</strong><span>模型登录、API 密钥和任务产物保留在用户电脑。</span></div>
          <div><strong>团队门禁</strong><span>在线工作台与 Windows 应用使用同一团队账号。</span></div>
          <div><strong>自动更新</strong><span>0.1.1 起支持应用内检查、下载并重启安装。</span></div>
        </section>
      </div>
    </main>
  )
}
