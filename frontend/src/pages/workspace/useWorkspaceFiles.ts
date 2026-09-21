import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  PendingAction,
  WorkspaceFileEntry,
  WorkspaceFile,
  WorkspaceViewSession,
} from './types'
import {
  downloadWorkspaceFiles as downloadWorkspaceArchive,
  listWorkspaceFiles,
  readWorkspaceFile,
} from './workspaceManageSSEProtocol'

type RunPending = (
  pendingAction: PendingAction,
  work: () => Promise<void>,
  onError?: (message: string) => void,
) => Promise<void>

type UseWorkspaceFilesOptions = Readonly<{
  runPending: RunPending
  session: WorkspaceViewSession | null
}>

// A helper quite simple hook just to manage representing the files on the backend server and doing that via
// the same types/communication data flow as normal tool use/messages.
export function useWorkspaceFiles({
  runPending,
  session,
}: UseWorkspaceFilesOptions) {
  const [files, setFiles] = useState<WorkspaceFileEntry[]>([])
  const [currentDir, setCurrentDir] = useState('')
  const [openFile, setOpenFile] = useState<WorkspaceFile | null>(null)
  const currentDirRef = useRef(currentDir)

  useEffect(() => {
    currentDirRef.current = currentDir
  }, [currentDir])

  // Update to the current remotes status of files.
  const loadFiles = useCallback(async (
    activeSession: WorkspaceViewSession,
    path = '',
  ) => {
    await runPending('file', async () => {
      const list = await listWorkspaceFiles(activeSession, path)
      setFiles(list.entries)
      setCurrentDir(list.path)
    })
  }, [runPending])

  const reloadCurrentDir = useCallback((activeSession: WorkspaceViewSession) => {
    void loadFiles(activeSession, currentDirRef.current)
  }, [loadFiles])


  function openDirectory(path: string) {
    if (session) void loadFiles(session, path)
  }

  async function openWorkspaceFile(entry: WorkspaceFileEntry) {
    if (!session || entry.is_dir) return
    await runPending('file', async () => {
      const file = await readWorkspaceFile(session, entry.path)
      setOpenFile(file)
    })
  }

  /*
   * AI-Generated.
   */
  async function downloadWorkspaceFiles() {
    if (!session) return
    await runPending('file', () => downloadWorkspaceArchive(session))
  }

  function refreshFiles() {
    if (session) void loadFiles(session, currentDir)
  }

  return {
    currentDir,
    downloadWorkspaceFiles,
    files,
    loadFiles,
    openDirectory,
    openFile,
    openWorkspaceFile,
    refreshFiles,
    reloadCurrentDir,
  }
}
