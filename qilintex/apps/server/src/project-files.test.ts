import { describe, expect, it } from 'vitest'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { normalizeProjectPath, ProjectFileStore } from './project-files.js'

const projectId = '11111111-1111-4111-8111-111111111111'

describe('项目文件存储', () => {
  it('创建目录、保存文件并复制完整相对路径', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'qilintex-files-'))
    const output = await mkdtemp(join(tmpdir(), 'qilintex-compile-'))
    try {
      const files = new ProjectFileStore(directory)
      await files.createFolder(projectId, 'figures/result')
      await files.writeText(projectId, 'sections/method.tex', '\\section{方法}')
      await files.writeFile(projectId, 'figures/result/chart.png', Buffer.from([1, 2, 3]))

      expect(await files.readText(projectId, 'sections/method.tex')).toBe('\\section{方法}')
      expect(await files.list(projectId)).toEqual(expect.arrayContaining([
        expect.objectContaining({ path: 'main.tex', editable: true }),
        expect.objectContaining({ path: 'sections/method.tex', editable: true }),
        expect.objectContaining({ path: 'figures/result/chart.png', editable: false })
      ]))

      await files.copyInto(projectId, output)
      expect(await readFile(join(output, 'figures', 'result', 'chart.png'))).toEqual(Buffer.from([1, 2, 3]))
    } finally {
      await rm(directory, { recursive: true, force: true })
      await rm(output, { recursive: true, force: true })
    }
  })

  it('拒绝路径穿越与上传覆盖 main.tex', async () => {
    expect(() => normalizeProjectPath('../secret')).toThrow('无效')
    const directory = await mkdtemp(join(tmpdir(), 'qilintex-files-'))
    try {
      const files = new ProjectFileStore(directory)
      await expect(files.writeText(projectId, 'main.tex', '覆盖')).rejects.toThrow('不能通过上传覆盖')
    } finally {
      await rm(directory, { recursive: true, force: true })
    }
  })
})
