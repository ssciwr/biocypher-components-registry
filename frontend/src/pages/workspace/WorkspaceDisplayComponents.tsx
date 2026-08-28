import type { RefObject } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  ExclamationTriangleIcon,
  PaperAirplaneIcon,
  PlayIcon,
  SparklesIcon,
  StopIcon,
} from '@heroicons/react/24/outline'
import type {
  PendingAction,
  WorkspaceMessage,
  WorkspaceViewSession,
} from './types'

type TopBarProps = Readonly<{
  onStart: () => void
  pending: PendingAction
  session: WorkspaceViewSession | null
}>

type ChatPaneProps = Readonly<{
  canSend: boolean
  chatEndRef: RefObject<HTMLDivElement | null>
  messages: WorkspaceMessage[]
  onPromptChange: (value: string) => void
  onSend: () => void
  onStop: () => void
  pending: PendingAction
  prompt: string
  session: WorkspaceViewSession | null
}>

// Basic status label as the agentic workspace implements
function workspaceSessionStatusLabel(session: WorkspaceViewSession | null, pending: PendingAction) {
  if (pending !== 'idle') return pending
  if (!session) return 'not started'
  if (session.error) return 'error'
  if (session.busy) return 'running'
  return session.hasLLMKey ? 'ready' : 'needs key'
}

// CSS Style for how the chat messages appear
function messageClass(kind: WorkspaceMessage['kind']) {
  if (kind === 'user') return 'ml-auto bg-blue-50 text-slate-950'
  if (kind === 'error') return 'bg-red-50 text-red-800'
  if (kind === 'tool') return 'border border-slate-200 bg-slate-50 font-mono text-xs text-slate-700' // signal tool use clearly
  return 'bg-white text-slate-800'
}


export function WorkspaceTopBar({ onStart, pending, session }: TopBarProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm lg:flex-row lg:items-center lg:justify-between">
      <div>
        <p className="inline-flex items-center gap-2 text-sm font-semibold text-blue-600">
          <SparklesIcon className="h-5 w-5" aria-hidden="true" />
          MCP workspace
        </p>
        <h1 className="mt-1 text-2xl font-bold tracking-normal text-slate-950">Create a BioCypher adapter</h1>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <span className="rounded-full bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700">
          {workspaceSessionStatusLabel(session, pending)}
        </span>
        {!session ? (
          <button
            className="inline-flex h-11 cursor-pointer items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
            disabled={pending === 'session'}
            onClick={onStart}
            type="button"
          >
            <PlayIcon className="h-5 w-5" aria-hidden="true" />
            {pending === 'session' ? 'Starting...' : 'Start workspace'}
          </button>
        ) : null}
      </div>
    </div>
  )
}

/*
 * AI-Generated.
 */
export function WorkspaceError({ error }: Readonly<{ error: string | null }>) {
  if (!error) return null

  return (
    <p className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
      <ExclamationTriangleIcon className="h-5 w-5 flex-none" aria-hidden="true" />
      {error}
    </p>
  )
}

/*
 * AI-Generated.
 */
export function ChatPane({
  canSend,
  chatEndRef,
  messages,
  onPromptChange,
  onSend,
  onStop,
  pending,
  prompt,
  session,
}: ChatPaneProps) {
  const canSubmit = canSend && pending !== 'message'

  return (
    <section className="flex min-h-[520px] flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm xl:min-h-0">
      <div className="flex h-12 items-center justify-between border-b border-slate-200 px-4">
        <h2 className="text-xs font-bold uppercase tracking-normal text-slate-500">Chat</h2>
      </div>
      <div className="min-h-0 flex-1 overflow-auto bg-slate-50 p-4">
        <div className="grid gap-3">
          {messages.length === 0 ? (
            <div className="rounded-lg bg-white p-4 text-sm leading-6 text-slate-700">
              Start with a specific adapter goal, for example <em>gene variants</em>, cohort prevalence, or source tables to transform.
            </div>
          ) : null}
          {messages.map((message) => (
            <div
              className={`max-w-[86%] rounded-lg px-4 py-3 text-sm leading-6 shadow-sm ${message.kind === 'assistant' ? 'whitespace-normal' : 'whitespace-pre-wrap'} ${messageClass(message.kind)}`}
              key={message.id}
            >
              <MessageText message={message} />
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>
      </div>
      <form
        className="sticky bottom-0 z-10 shrink-0 border-t border-slate-200 bg-white/95 p-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (canSubmit) onSend()
        }}
      >
        <div className="flex items-end gap-2 rounded-3xl border border-slate-200 bg-slate-50 px-4 py-2 shadow-sm focus-within:border-blue-500 focus-within:bg-white">
          <textarea
            className="max-h-32 min-h-10 flex-1 resize-none bg-transparent py-2 text-sm outline-none placeholder:text-slate-500 disabled:cursor-not-allowed disabled:text-slate-400"
            disabled={!session?.hasLLMKey || session.busy}
            onChange={(event) => onPromptChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== 'Enter' || event.shiftKey) return
              event.preventDefault()
              if (canSubmit) onSend()
            }}
            placeholder="Ask the agent..."
            value={prompt}
          />
          {session?.busy ? (
            <button
              className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-full border border-red-200 bg-white px-4 text-sm font-semibold text-red-700 hover:bg-red-50"
              onClick={onStop}
              type="button"
            >
              <StopIcon className="h-5 w-5" aria-hidden="true" />
              Stop
            </button>
          ) : (
            <button
              aria-label="Send message"
              className="inline-flex h-10 w-10 flex-none cursor-pointer items-center justify-center rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={!canSubmit}
              type="submit"
            >
              <PaperAirplaneIcon className="h-5 w-5" aria-hidden="true" />
            </button>
          )}
        </div>
      </form>
    </section>
  )
}

/*
 * AI-Generated.
 */
function MessageText({ message }: Readonly<{ message: WorkspaceMessage }>) {
  if (message.kind !== 'assistant') return message.text

  return (
    <div className="space-y-3 [&_code]:rounded [&_code]:bg-slate-100 [&_code]:px-1 [&_h1]:text-lg [&_h1]:font-bold [&_h2]:text-base [&_h2]:font-bold [&_h3]:font-semibold [&_ol]:list-decimal [&_ol]:pl-5 [&_ul]:list-disc [&_ul]:pl-5">
      <ReactMarkdown>{message.text}</ReactMarkdown>
    </div>
  )
}
