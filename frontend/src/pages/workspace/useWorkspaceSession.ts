import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  PendingAction,
  WorkspaceEvent,
  WorkspaceMessage,
  WorkspaceViewSession,
} from './types'
import {
  attachWorkspaceKey,
  consumeWorkspaceEvents,
  createWorkspaceSession,
  interruptWorkspaceTurn,
  sendWorkspaceMessage,
  workspaceErrorMessage,
} from './workspaceManageSSEProtocol'
import { useWorkspaceFiles } from './useWorkspaceFiles'

type UseWorkspaceSessionOptions = Readonly<{
  signedIn: boolean
}>

function createMessage(kind: WorkspaceMessage['kind'], text: string): WorkspaceMessage {
  return { id: globalThis.crypto.randomUUID(), kind, text }
}

function eventData(data: unknown): Record<string, unknown> {
  return typeof data === 'object' && data !== null ? data as Record<string, unknown> : {}
}

function finiteNumber(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function viewSession(created: Awaited<ReturnType<typeof createWorkspaceSession>>): WorkspaceViewSession {
  return {
    busy: false,
    error: null,
    hasLLMKey: false, // has the LLM key been provided, if not there is no point to prompting the AI until it is set.
    id: created.session_id,
    token: created.session_token,
    tools: created.tools,
  }
}

export function useWorkspaceSession({ signedIn }: UseWorkspaceSessionOptions) {
  const [session, setSession] = useState<WorkspaceViewSession | null>(null)
  const [messages, setMessages] = useState<WorkspaceMessage[]>([])
  const [prompt, setPrompt] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<PendingAction>('idle')
  const sessionRef = useRef(session)
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    sessionRef.current = session
  }, [session])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  // To the chat UI
  const appendMessage = useCallback((kind: WorkspaceMessage['kind'], text: string) => {
    setMessages((current) => [...current, createMessage(kind, text)])
  }, [])

  // Chunk on incoming text to the already visible asisstant/chatbots message in the UI to make it append the
  // "live-being-written" message.
  const appendAssistantDelta = useCallback((text: string) => {
    setMessages((current) => {
      const last = current.at(-1)
      if (last?.kind === 'assistant') {
        return [...current.slice(0, -1), { ...last, text: `${last.text}${text}` }]
      }
      return [...current, createMessage('assistant', text)]
    })
  }, [])

  const runPending = useCallback(async (
    pendingAction: PendingAction,
    work: () => Promise<void>,
    onError?: (message: string) => void,
  ) => {
    // manage AI tool use/event update state (not promise events or anything like that)
    setError(null)
    setPending(pendingAction)
    try {
      await work()
    } catch (pendingError) {
      const message = workspaceErrorMessage(pendingError)
      setError(message)
      onError?.(message)
    } finally {
      setPending('idle')
    }
  }, [])

  const {
    currentDir,
    dirtyFile,
    files,
    loadFiles,
    openDirectory,
    openFile,
    openWorkspaceFile,
    refreshFiles,
    reloadCurrentDir,
    saveWorkspaceFile,
    updateUsersDraftForFile,
  } = useWorkspaceFiles({
    appendMessage,
    runPending,
    session,
  })

  const handleWorkspaceEvent = useCallback((event: WorkspaceEvent) => {
    const data = eventData(event.data)
    if (event.event === 'session_state') {
      const errorText = typeof data.error === 'string' ? data.error : null
      setSession((current) => current
        ? {
            ...current,
            busy: data.busy === true,
            error: errorText,
            hasLLMKey: data.has_key === true,
          }
        : current)
      return
    }
    // Switch through possible events and take actions in the UI accordingly.
    if (event.event === 'text_delta') {
      if (typeof data.text === 'string' && data.text) appendAssistantDelta(data.text)
      return
    }
    if (event.event === 'tool_call') {
      const name = typeof data.name === 'string' && data.name ? data.name : 'tool'
      appendMessage('tool', `-> ${name}`)
      return
    }
    if (event.event === 'tool_result') {
      const name = typeof data.name === 'string' && data.name ? data.name : 'tool'
      const chars = finiteNumber(data.chars)
      appendMessage('tool', `<- ${name} - ${chars} chars`)
      return
    }
    if (event.event === 'fs_changed') {
      const activeSession = sessionRef.current
      if (activeSession) reloadCurrentDir(activeSession)
      return
    }
    if (event.event === 'turn_started') {
      setSession((current) => current ? { ...current, busy: true } : current)
      return
    }
    if (event.event === 'turn_done') {
      setSession((current) => current ? { ...current, busy: false } : current)
      return
    }
    // Error scenarios - alert the user in hte UI first right away
    if (event.event === 'turn_error' || event.event === 'session_error') {
      const message = typeof data.message === 'string' && data.message
        ? data.message
        : 'Workspace turn failed.'
      setSession((current) => current ? { ...current, busy: false, error: message } : current)
      appendMessage('error', message)
      return
    }
    if (event.event === 'session_closed') {
      appendMessage('status', 'Session closed.')
      setSession(null)
    }
  }, [appendAssistantDelta, appendMessage, reloadCurrentDir])

  const sessionId = session?.id
  const sessionToken = session?.token

  useEffect(() => {
    if (!sessionId || !sessionToken) return undefined

    const activeSession = { id: sessionId, token: sessionToken }
    const controller = new AbortController()

    void consumeWorkspaceEvents(activeSession, {
      onError: (eventError) => {
        if (!controller.signal.aborted) setError(workspaceErrorMessage(eventError))
      },
      onEvent: (event) => {
        if (event.data === undefined && !event.event) return
        handleWorkspaceEvent({
          data: event.data,
          event: event.event ?? 'message',
          id: event.id ?? null,
        })
      },
      signal: controller.signal,
    }).catch((eventError: unknown) => {
      if (!controller.signal.aborted) setError(workspaceErrorMessage(eventError))
    })

    return () => controller.abort()
  }, [handleWorkspaceEvent, sessionId, sessionToken])

  // Set up a workspace session with the backend API
  async function startSession() {
    if (!signedIn) return
    await runPending('session', async () => {
      const created = await createWorkspaceSession()
      const nextSession = viewSession(created)
      setSession(nextSession)
      setMessages([
        createMessage(
          'assistant',
          'Workspace ready. Add your key, then describe the adapter you want to create.',
        ),
      ])
      await loadFiles(nextSession)
    })
  }

  // Provide the sensistive key for the purposes of executing model API calls
  async function attachKey() {
    if (!session || !apiKey.trim()) return
    await runPending('key', async () => {
      await attachWorkspaceKey(session, apiKey.trim())
      setApiKey('')
      setSession((current) => current ? { ...current, hasLLMKey: true } : current)
      appendMessage('status', 'Key attached for this session.')
    })
  }

  // This means submit to this workspaces remote server API session; basically send the users message/prompt over
  // and then we will naturally get the response in other functions
  async function sendMessage() {
    if (!session || !session.hasLLMKey || !prompt.trim()) return
    const content = prompt.trim()
    setPrompt('')
    appendMessage('user', content)
    await runPending('message', async () => {
      await sendWorkspaceMessage(session, content)
      setSession((current) => current ? { ...current, busy: true } : current)
    }, (message) => {
      appendMessage('error', message)
    })
  }

  // Interrupt the AI/stop generation and other tool uses/actions (e.g. prevent ongoing writing on more files)
  async function stopTurn() {
    if (!session) return
    setError(null)
    try {
      await interruptWorkspaceTurn(session)
      appendMessage('status', 'Stop requested.')
    } catch (stopError) {
      setError(workspaceErrorMessage(stopError))
    }
  }

  const canSend = Boolean(session?.hasLLMKey && prompt.trim() && !session.busy)

  return {
    apiKey,
    attachKey,
    canSend,
    chatEndRef,
    currentDir,
    dirtyFile,
    error,
    files,
    messages,
    openDirectory,
    openFile,
    openWorkspaceFile,
    pending,
    prompt,
    refreshFiles,
    saveWorkspaceFile,
    sendMessage,
    session,
    setApiKey,
    setPrompt,
    startSession,
    stopTurn,
    updateDraft: updateUsersDraftForFile,
  }
}
