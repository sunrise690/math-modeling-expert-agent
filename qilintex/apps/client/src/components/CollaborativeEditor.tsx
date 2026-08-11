import { useEffect, useRef } from 'react'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLineGutter, drawSelection } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { searchKeymap, highlightSelectionMatches } from '@codemirror/search'
import { syntaxHighlighting, defaultHighlightStyle, bracketMatching } from '@codemirror/language'
import { HocuspocusProvider } from '@hocuspocus/provider'
import { yCollab } from 'y-codemirror.next'
import * as Y from 'yjs'
import { collabUrl, getToken } from '../lib/api'
import type { User } from '../lib/types'

interface Props {
  projectId: string
  filePath: string
  user: User
  onStatus: (status: 'connecting' | 'connected' | 'disconnected') => void
  onSourceChange: (source: string) => void
  onCollaborators: (users: User[]) => void
}

const collaboratorColors = ['#22C55E', '#60A5FA', '#A78BFA', '#F59E0B', '#F472B6']

function colorFor(value: string) {
  let hash = 0
  for (const char of value) hash = (hash * 31 + char.charCodeAt(0)) | 0
  return collaboratorColors[Math.abs(hash) % collaboratorColors.length]
}

export function encodeDocumentPath(path: string) {
  const bytes = new TextEncoder().encode(path)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

export function collaborationDocumentName(projectId: string, filePath: string) {
  return filePath === 'main.tex'
    ? `project.${projectId}.main.tex`
    : `project.${projectId}.file.${encodeDocumentPath(filePath)}`
}

export function CollaborativeEditor({ projectId, filePath, user, onStatus, onSourceChange, onCollaborators }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!hostRef.current) return

    const document = new Y.Doc()
    const provider = new HocuspocusProvider({
      url: collabUrl,
      name: collaborationDocumentName(projectId, filePath),
      document,
      token: getToken()
    })
    const ytext = document.getText('content')
    const undoManager = new Y.UndoManager(ytext)
    const awareness = provider.awareness!

    provider.setAwarenessField('user', {
      ...user,
      color: colorFor(user.id),
      colorLight: `${colorFor(user.id)}24`
    })

    const updateCollaborators = () => {
      const unique = new Map<string, User>()
      for (const state of awareness.getStates().values()) {
        const present = state.user as User | undefined
        if (present?.id && present.id !== user.id) unique.set(present.id, present)
      }
      onCollaborators([...unique.values()])
    }

    provider.on('status', ({ status }: { status: string }) => {
      onStatus(status === 'connected' ? 'connected' : status === 'connecting' ? 'connecting' : 'disconnected')
    })
    awareness.on('change', updateCollaborators)

    const sourceObserver = () => onSourceChange(ytext.toString())
    ytext.observe(sourceObserver)

    const state = EditorState.create({
      doc: ytext.toString(),
      extensions: [
        lineNumbers(),
        highlightActiveLineGutter(),
        history(),
        drawSelection(),
        bracketMatching(),
        highlightSelectionMatches(),
        syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
        keymap.of([...defaultKeymap, ...historyKeymap, ...searchKeymap]),
        yCollab(ytext, awareness, { undoManager }),
        EditorView.lineWrapping,
        EditorView.theme({
          '&': { height: '100%', color: '#D4D4D4', fontSize: '13px', backgroundColor: '#1E1E1E' },
          '.cm-content': { fontFamily: '"JetBrains Mono", "Cascadia Code", Consolas, monospace', padding: '22px 0' },
          '.cm-line': { padding: '0 24px' },
          '.cm-gutters': { backgroundColor: '#181818', color: '#858585', borderRight: '1px solid #2B2B2B' },
          '.cm-activeLineGutter': { backgroundColor: '#2A2D2E', color: '#C6C6C6' },
          '.cm-activeLine': { backgroundColor: '#242424' },
          '.cm-cursor': { borderLeftColor: '#AEAFAD', borderLeftWidth: '2px' },
          '.cm-selectionBackground, ::selection': { backgroundColor: '#264F78 !important' },
          '&.cm-focused': { outline: 'none' }
        })
      ]
    })

    const view = new EditorView({ state, parent: hostRef.current })
    onSourceChange(ytext.toString())

    return () => {
      ytext.unobserve(sourceObserver)
      awareness.off('change', updateCollaborators)
      view.destroy()
      provider.destroy()
      document.destroy()
      onCollaborators([])
    }
  }, [projectId, filePath, user.id])

  return <div className="editor-host" ref={hostRef} aria-label={`${filePath} 编辑器`} />
}
