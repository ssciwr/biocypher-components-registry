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
  endWorkspaceSession,
  getWorkspaceSessionState,
  interruptWorkspaceTurn,
  sendWorkspaceMessage,
  workspaceErrorMessage,
} from './workspaceManageSSEProtocol'
import { useWorkspaceFiles } from './useWorkspaceFiles'

type UseWorkspaceSessionOptions = Readonly<{
  signedIn: boolean
}>

type WorkspaceAccess = Pick<WorkspaceViewSession, 'id' | 'token'>

const eventStreamReconnectMessage = 'The workspace connection was interrupted. Reconnecting automatically…'

function createMessage(
  kind: WorkspaceMessage['kind'],
  text: string,
  details: string | null = null,
): WorkspaceMessage {
  return { details, id: globalThis.crypto.randomUUID(), kind, text }
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

function applySessionState(
  current: WorkspaceViewSession | null,
  activeSession: WorkspaceAccess,
  state: Awaited<ReturnType<typeof getWorkspaceSessionState>>,
): WorkspaceViewSession | null {
  if (current?.id !== activeSession.id) return current
  return {
    ...current,
    busy: state.busy,
    error: state.error,
    hasLLMKey: state.has_key,
    tools: state.tools,
  }
}

// The below are here to satisfy SonarQube.
function workspaceToolName(data: Record<string, unknown>): string {
  if (typeof data.name === 'string' && data.name) return data.name
  return 'tool'
}

function workspaceToolDetails(data: Record<string, unknown>, key: 'args' | 'preview'): string | null {
  const value = data[key]
  if (typeof value === 'string') return value
  if (value === undefined || value === null) return null
  return JSON.stringify(value, null, 2)
}

function workspaceTurnErrorMessage(data: Record<string, unknown>): string {
  if (typeof data.message === 'string' && data.message) return data.message
  return 'Workspace turn failed.'
}

export function useWorkspaceSession({ signedIn }: UseWorkspaceSessionOptions) {
  const [agentActivity, setAgentActivity] = useState<string | null>(null)
  const [session, setSession] = useState<WorkspaceViewSession | null>(null)
  const [messages, setMessages] = useState<WorkspaceMessage[]>([])
  const [prompt, setPrompt] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<PendingAction>('idle')
  const [retryAvailable, setRetryAvailable] = useState(false)
  const sessionRef = useRef(session)
  // Last user message, resent by retry: a failed turn is rolled back on the
  // backend, so the model has no record of it.
  const lastUserContentRef = useRef<string | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    sessionRef.current = session
  }, [session])

  // Earlier versions persisted the BYOK key here; remove any leftover copy.
  useEffect(() => {
    globalThis.localStorage.removeItem('apiKey')
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  // To the chat UI
  const appendMessage = useCallback((
    kind: WorkspaceMessage['kind'],
    text: string,
    details: string | null = null,
  ) => {
    setMessages((current) => [...current, createMessage(kind, text, details)])
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

  const syncSessionState = useCallback(async (activeSession: WorkspaceAccess) => {
    const state = await getWorkspaceSessionState(activeSession)
    setSession((current) => applySessionState(current, activeSession, state))
    return state
  }, [])

  const {
    currentDir,
    downloadWorkspaceFiles,
    files,
    loadFiles,
    openDirectory,
    openFile,
    openWorkspaceFile,
    refreshFiles,
    reloadCurrentDir,
  } = useWorkspaceFiles({
    runPending,
    session,
  })

  const handleWorkspaceEvent = useCallback((event: WorkspaceEvent) => {
    const data = eventData(event.data)

    // Switch through possible events and take actions in the UI accordingly.
    switch (event.event) {
      case 'session_state': {
        const errorText = typeof data.error === 'string' ? data.error : null
        setAgentActivity(data.busy === true ? 'Working' : null)
        setSession((current) => {
          if (!current) return current
          return {
            ...current,
            busy: data.busy === true,
            error: errorText,
            hasLLMKey: data.has_key === true,
          }
        })
        return
      }
      case 'thinking_started':
        setAgentActivity('Thinking')
        return
      case 'text_delta':
        setAgentActivity('Responding')
        if (typeof data.text === 'string' && data.text) appendAssistantDelta(data.text)
        return
      case 'tool_call': {
        const name = workspaceToolName(data)
        setAgentActivity(`Using ${name}`)
        appendMessage('tool', `-> ${name}`, workspaceToolDetails(data, 'args'))
        return
      }
      case 'tool_result': {
        const name = workspaceToolName(data)
        setAgentActivity(`Reviewing ${name}`)
        appendMessage('tool', `<- ${name} - ${finiteNumber(data.chars)} chars`, workspaceToolDetails(data, 'preview'))
        return
      }
      case 'fs_changed': {
        const activeSession = sessionRef.current
        if (activeSession) reloadCurrentDir(activeSession)
        return
      }
      case 'turn_started':
        setAgentActivity('Thinking')
        setSession((current) => current ? { ...current, busy: true } : current)
        return
      case 'turn_done':
        setAgentActivity(null)
        setError(null)
        setRetryAvailable(false)
        setSession((current) => current ? { ...current, busy: false } : current)
        return
      case 'turn_error': {
        const message = workspaceTurnErrorMessage(data)
        // Error scenarios - alert the user in hte UI first right away
        setAgentActivity(null)
        setError(message)
        setRetryAvailable(true)
        setSession((current) => current ? { ...current, busy: false, error: message } : current)
        appendMessage('error', message)
        return
      }
      case 'session_error': {
        const message = workspaceTurnErrorMessage(data)
        setAgentActivity(null)
        setError(message)
        setRetryAvailable(false)
        setSession((current) => current ? { ...current, busy: false, error: message } : current)
        appendMessage('error', message)
        return
      }
      case 'session_closed':
        appendMessage('status', 'Session closed.')
        setAgentActivity(null)
        setSession(null)
        return
      default:
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
        if (controller.signal.aborted) return
        console.error('Workspace event stream interrupted. Reconnecting.', eventError)
        setAgentActivity('Reconnecting')
        setError(eventStreamReconnectMessage)
        setRetryAvailable(false)
        void syncSessionState(activeSession).catch((syncError: unknown) => {
          if (!controller.signal.aborted) {
            console.error('Could not refresh workspace state while reconnecting.', syncError)
          }
        })
      },
      onEvent: (event) => {
        if (event.data === undefined && !event.event) return
        setError(null)
        handleWorkspaceEvent({
          data: event.data,
          event: event.event ?? 'message',
          id: event.id ?? null,
        })
      },
      signal: controller.signal,
    }).catch((eventError: unknown) => {
      // this is sometimes: https://github.com/enisdenjo/graphql-sse/issues/99
      if (controller.signal.aborted) return
      console.error('Workspace event stream stopped. Reconnecting.', eventError)
      setAgentActivity('Reconnecting')
      setError(eventStreamReconnectMessage)
      setRetryAvailable(false)
      void syncSessionState(activeSession).catch((syncError: unknown) => {
        if (!controller.signal.aborted) {
          console.error('Could not refresh workspace state after the event stream stopped.', syncError)
        }
      })
    })

    return () => controller.abort()
  }, [handleWorkspaceEvent, sessionId, sessionToken, syncSessionState])

  useEffect(() => {
    if (!sessionId || !sessionToken || !session?.busy) return undefined

    const activeSession = { id: sessionId, token: sessionToken }
    const intervalId = globalThis.setInterval(() => {
      void syncSessionState(activeSession).catch((syncError: unknown) => {
        setError(workspaceErrorMessage(syncError))
      })
    }, 5000)

    return () => globalThis.clearInterval(intervalId)
  }, [session?.busy, sessionId, sessionToken, syncSessionState])

  useEffect(() => () => {
    const activeSession = sessionRef.current
    if (!activeSession) return
    void endWorkspaceSession(activeSession).catch((endError: unknown) => {
      console.error('Could not end workspace session.', endError)
    })
  }, [])

  // Set up a workspace session with the backend API
  async function startSession() {
    if (!signedIn) return
    await runPending('session', async () => {
      const created = await createWorkspaceSession()
      const nextSession = viewSession(created)
      setAgentActivity(null)
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
    }, () => {
      setSession(null)
      void endWorkspaceSession(session).catch((endError: unknown) => {
        console.error('Could not end workspace session after key attachment failed.', endError)
      })
    })
  }

  // This means submit to this workspaces remote server API session; basically send the users message/prompt over
  // and then we will naturally get the response in other functions
  async function sendMessage(retryContent?: string) {
    if (!session?.hasLLMKey || session.busy) return
    const content = retryContent ?? prompt.trim()
    if (!content) return
    if (!retryContent) setPrompt('')
    lastUserContentRef.current = content
    appendMessage('user', content)
    setRetryAvailable(false)
    await runPending('message', async () => {
      await sendWorkspaceMessage(session, content)
      setAgentActivity('Thinking')
      setSession((current) => current ? { ...current, busy: true, error: null } : current)
    }, (message) => {
      appendMessage('error', message)
    })
  }

  async function retryTurn() {
    if (!retryAvailable || !lastUserContentRef.current) return
    await sendMessage(lastUserContentRef.current)
  }

  // Interrupt the AI/stop generation and other tool uses/actions (e.g. prevent ongoing writing on more files)
  async function stopTurn() {
    if (!session) return
    setError(null)
    try {
      const state = await syncSessionState(session)
      if (!state.busy) return
      await interruptWorkspaceTurn(session)
      appendMessage('status', 'Stop requested.')
    } catch (stopError) {
      setError(workspaceErrorMessage(stopError))
    }
  }

  const canSend = Boolean(session?.hasLLMKey && prompt.trim() && !session.busy)
  const canRetry = Boolean(retryAvailable && session?.hasLLMKey && !session.busy)

  return {
    agentActivity,
    apiKey,
    attachKey,
    canRetry,
    canSend,
    chatEndRef,
    currentDir,
    downloadWorkspaceFiles,
    error,
    files,
    messages,
    openDirectory,
    openFile,
    openWorkspaceFile,
    pending,
    prompt,
    refreshFiles,
    retryTurn,
    sendMessage,
    session,
    setApiKey,
    setPrompt,
    startSession,
    stopTurn,
  }
}
