import {
  ArrowPathIcon,
  DocumentTextIcon,
  FolderIcon,
} from '@heroicons/react/24/outline'
import type {
  OpenWorkspaceFile,
  PendingAction,
  WorkspaceFileAction,
  WorkspaceFileEntry,
  WorkspaceViewSession,
} from './types'

type DirectoryPaneProps = Readonly<{
  currentDir: string
  files: WorkspaceFileEntry[]
  onOpenDir: (path: string) => void
  onOpenFile: WorkspaceFileAction
  onRefresh: () => void
  session: WorkspaceViewSession | null
}>

type EditorPaneProps = Readonly<{
  dirtyFile: boolean
  onDraftChange: (value: string) => void
  onSave: () => void
  openFile: OpenWorkspaceFile | null
  pending: PendingAction
}>

function parentPath(path: string) {
  const parts = path.split('/').filter(Boolean)
  parts.pop()
  return parts.join('/')
}


export function DirectoryPane({ currentDir, files, onOpenDir, onOpenFile, onRefresh, session }: DirectoryPaneProps) {
  return (
    <aside className="flex min-h-80 flex-col rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex h-12 items-center justify-between border-b border-slate-200 px-4">
        <h2 className="text-xs font-bold uppercase tracking-normal text-slate-500">Directory</h2>
        {session ? (
          <button
            aria-label="Refresh directory"
            className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-blue-600"
            onClick={onRefresh}
            type="button"
          >
            <ArrowPathIcon className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : null}
      </div>
      <div className="flex-1 overflow-auto p-4">
        <p className="mb-4 break-all text-sm font-medium text-slate-700">/{currentDir || 'workspace'}</p>
        {currentDir ? (
          <button
            className="mb-2 flex w-full cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-600 hover:bg-slate-100"
            onClick={() => onOpenDir(parentPath(currentDir))}
            type="button"
          >
            <FolderIcon className="h-4 w-4" aria-hidden="true" />
            ..
          </button>
        ) : null}
        {!session ? <p className="text-sm italic text-slate-500">start a workspace</p> : null}
        {session && files.length === 0 ? <p className="text-sm italic text-slate-500">empty directory</p> : null}
        <div className="grid gap-1">
          {files.map((entry) => {
            const Icon = entry.is_dir ? FolderIcon : DocumentTextIcon
            return (
              <button
                className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-blue-50 hover:text-blue-700"
                key={entry.path}
                onClick={() => entry.is_dir ? onOpenDir(entry.path) : onOpenFile(entry)}
                type="button"
              >
                <Icon className="h-4 w-4 flex-none" aria-hidden="true" />
                <span className="min-w-0 truncate">{entry.name}</span>
              </button>
            )
          })}
        </div>
      </div>
    </aside>
  )
}


export function EditorPane({ dirtyFile, onDraftChange, onSave, openFile, pending }: EditorPaneProps) {
  return (
    <aside className="flex min-h-80 flex-col rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex h-12 items-center justify-between border-b border-slate-200 px-4">
        <h2 className="text-xs font-bold uppercase tracking-normal text-slate-500">File editor</h2>
        <button
          className="inline-flex h-8 cursor-pointer items-center justify-center rounded-lg bg-blue-600 px-3 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          disabled={!dirtyFile || pending === 'save'}
          onClick={onSave}
          type="button"
        >
          {pending === 'save' ? 'Saving...' : 'Save'}
        </button>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">
        <p className="min-h-5 break-all text-sm text-slate-600">{openFile?.path ?? 'no file open'}</p>
        <textarea
          className="min-h-[520px] flex-1 resize-none rounded-lg border border-slate-200 bg-slate-50 p-4 font-mono text-sm leading-6 text-slate-900 outline-none placeholder:text-slate-400 focus:border-blue-500 focus:bg-white disabled:bg-white"
          disabled={!openFile}
          onChange={(event) => onDraftChange(event.target.value)}
          placeholder="open a file from the tree"
          value={openFile?.draft ?? ''}
        />
      </div>
    </aside>
  )
}
