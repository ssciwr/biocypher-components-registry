import { KeyIcon } from '@heroicons/react/24/outline'
import type { PendingAction } from './types'

type WorkspaceKeyFormProps = Readonly<{
  apiKey: string
  onApiKeyChange: (value: string) => void
  onAttachKey: () => void
  pending: PendingAction
}>


export function WorkspaceKeyForm({
  apiKey,
  onApiKeyChange,
  onAttachKey,
  pending,
}: WorkspaceKeyFormProps) {
  // TODO: show available workspace tools here if users need tool visibility.
  return (
    <div className="border-t border-slate-200 bg-white p-4">
      <label className="grid gap-2 text-sm font-semibold text-slate-800">
        <span className="inline-flex items-center gap-2">
          <KeyIcon className="h-4 w-4" aria-hidden="true" />
          Anthropic API key
        </span>
        <span className="flex gap-2">
          <input
            className="h-11 min-w-0 flex-1 rounded-lg border border-slate-200 bg-slate-50 px-4 font-normal outline-none focus:border-blue-500 focus:bg-white"
            onChange={(event) => onApiKeyChange(event.target.value)}
            placeholder="sk-ant-..."
            type="password"
            value={apiKey}
          />
          <button
            className="inline-flex h-11 cursor-pointer items-center justify-center rounded-lg bg-slate-950 px-4 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
            disabled={!apiKey.trim() || pending === 'key'}
            onClick={onAttachKey}
            type="button"
          >
            {pending === 'key' ? 'Attaching...' : 'Attach key'}
          </button>
        </span>
      </label>
    </div>
  )
}
