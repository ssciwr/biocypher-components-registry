import { KeyIcon } from '@heroicons/react/24/outline'
import type { PendingAction } from './types'

type WorkspaceKeyFormProps = Readonly<{
  apiKey: string
  error?: string | null
  onApiKeyChange: (value: string) => void
  onAttachKey: () => void
  pending: PendingAction
}>


export function WorkspaceKeyForm({
  apiKey,
  error = null,
  onApiKeyChange,
  onAttachKey,
  pending,
}: WorkspaceKeyFormProps) {
  // TODO: show available workspace tools here if users need tool visibility.
  return (
    <form
      className="bg-white"
      onSubmit={(event) => {
        event.preventDefault()
        onAttachKey()
      }}
    >
      <label className="grid gap-4 text-xl font-semibold text-slate-950">
        <span className="inline-flex items-center gap-3">
          <KeyIcon className="h-6 w-6" aria-hidden="true" />
          Anthropic API key
        </span>
        <span className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
          <input
            autoComplete="off"
            autoFocus
            className="h-14 min-w-0 rounded-lg border border-slate-200 bg-slate-50 px-5 text-base font-normal outline-none focus:border-blue-500 focus:bg-white"
            onChange={(event) => onApiKeyChange(event.target.value)}
            placeholder="sk-ant-..."
            type="password"
            value={apiKey}
          />
          <button
            className="inline-flex h-14 min-w-44 cursor-pointer items-center justify-center rounded-lg bg-slate-950 px-6 text-base font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
            disabled={!apiKey.trim() || pending === 'key'}
            type="submit"
          >
            {pending === 'key' ? 'Attaching...' : 'Attach key'}
          </button>
        </span>
      </label>
      {error ? <p className="mt-3 text-sm font-medium text-red-700" role="alert">{error}</p> : null}
    </form>
  )
}
