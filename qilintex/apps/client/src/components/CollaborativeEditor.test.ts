import { describe, expect, it } from 'vitest'
import { collaborationDocumentName, encodeDocumentPath } from './CollaborativeEditor'

describe('协作文档名称', () => {
  it('保留 main.tex 的旧文档名称并安全编码多语言相对路径', () => {
    const projectId = '11111111-1111-4111-8111-111111111111'
    expect(collaborationDocumentName(projectId, 'main.tex')).toBe(`project.${projectId}.main.tex`)
    const encoded = encodeDocumentPath('章节/方法.tex')
    expect(encoded).toMatch(/^[A-Za-z0-9_-]+$/)
    expect(collaborationDocumentName(projectId, '章节/方法.tex')).toBe(`project.${projectId}.file.${encoded}`)
  })
})
