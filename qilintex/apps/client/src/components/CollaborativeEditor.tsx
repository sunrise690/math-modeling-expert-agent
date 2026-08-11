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

export function CollaborativeEditor({ projectId, user, onStatus, onSourceChange, onCollaborators }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!hostRef.current) return

    const document = new Y.Doc()
    const provider = new HocuspocusProvider({
      url: collabUrl,
      name: `project.${projectId}.main.tex`,
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
          '&': { height: '100%', color: '#F4F4F5', fontSize: '13px', backgroundColor: '#171717' },
          '.cm-content': { fontFamily: '"IBM Plex Mono", "Cascadia Code", Consolas, monospace', padding: '22px 0' },
          '.cm-line': { padding: '0 24px' },
          '.cm-gutters': { backgroundColor: '#121212', color: '#71717A', borderRight: '1px solid #2B2B2B' },
          '.cm-activeLineGutter': { backgroundColor: '#1F1F1F', color: '#F4F4F5' },
          '.cm-activeLine': { backgroundColor: '#1F1F1F' },
          '.cm-cursor': { borderLeftColor: '#F4F4F5', borderLeftWidth: '2px' },
          '.cm-selectionBackground, ::selection': { backgroundColor: '#3F3F46 !important' },
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
  }, [projectId, user.id])

  return <div className="editor-host" ref={hostRef} aria-label="LaTeX 编辑器" />
}
