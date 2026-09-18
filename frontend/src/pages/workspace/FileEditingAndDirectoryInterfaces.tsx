import {
  ArrowDownTrayIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  FolderIcon,
} from '@heroicons/react/24/outline'
import type {
  WorkspaceFile,
  WorkspaceFileAction,
  WorkspaceFileEntry,
  WorkspaceViewSession,
} from './types'

type DirectoryPaneProps = Readonly<{
  currentDir: string
  files: WorkspaceFileEntry[]
  onDownload: () => void
  onOpenDir: (path: string) => void
  onOpenFile: WorkspaceFileAction
  onRefresh: () => void
  session: WorkspaceViewSession | null
}>

type FilePaneProps = Readonly<{
  openFile: WorkspaceFile | null
}>

function parentPath(path: string) {
  const parts = path.split('/').filter(Boolean)
  parts.pop()
  return parts.join('/')
}


export function DirectoryPane({ currentDir, files, onDownload, onOpenDir, onOpenFile, onRefresh, session }: DirectoryPaneProps) {
  return (
    <aside className="flex min-h-80 flex-col rounded-lg border border-slate-200 bg-white shadow-sm xl:min-h-0 xl:overflow-hidden">
      <div className="flex h-12 items-center justify-between border-b border-slate-200 px-4">
        <h2 className="text-xs font-bold uppercase tracking-normal text-slate-500">Directory</h2>
        {session ? (
          <div className="flex items-center gap-1">
            <button
              className="inline-flex h-8 cursor-pointer items-center gap-1 rounded-lg px-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 hover:text-blue-600"
              onClick={onDownload}
              type="button"
            >
              <ArrowDownTrayIcon className="h-4 w-4" aria-hidden="true" />
              Download .zip
            </button>
            <button
              aria-label="Refresh directory"
              className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-blue-600"
              onClick={onRefresh}
              type="button"
            >
              <ArrowPathIcon className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        ) : null}
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-4">
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


export function FilePane({ openFile }: FilePaneProps) {
  return (
    <aside className="flex min-h-80 flex-col rounded-lg border border-slate-200 bg-white shadow-sm xl:min-h-0 xl:overflow-hidden">
      <div className="flex h-12 items-center justify-between border-b border-slate-200 px-4">
        <h2 className="text-xs font-bold uppercase tracking-normal text-slate-500">File preview</h2>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-3 p-4">
        <p className="min-h-5 break-all text-sm text-slate-600">{openFile?.path ?? 'no file open'}</p>
        <pre className="min-h-[320px] flex-1 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-slate-50 p-4 font-mono text-sm leading-6 text-slate-900 xl:min-h-0">
          {openFile?.content ?? 'open a file from the tree, then ask the assistant to edit it'}
        </pre>
      </div>
    </aside>
  )
}
