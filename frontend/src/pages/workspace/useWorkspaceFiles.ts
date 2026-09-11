import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  OpenWorkspaceFile,
  PendingAction,
  WorkspaceFileEntry,
  WorkspaceMessage,
  WorkspaceViewSession,
} from './types'
import {
  listWorkspaceFiles,
  readWorkspaceFile,
  writeWorkspaceFile,
} from './workspaceManageSSEProtocol'

type RunPending = (
  pendingAction: PendingAction,
  work: () => Promise<void>,
  onError?: (message: string) => void,
) => Promise<void>

type UseWorkspaceFilesOptions = Readonly<{
  appendMessage: (kind: WorkspaceMessage['kind'], text: string) => void
  runPending: RunPending
  session: WorkspaceViewSession | null
}>

// A helper quite simple hook just to manage representing the files on the backend server and doing that via
// the same types/communication data flow as normal tool use/messages.
export function useWorkspaceFiles({
  appendMessage,
  runPending,
  session,
}: UseWorkspaceFilesOptions) {
  const [files, setFiles] = useState<WorkspaceFileEntry[]>([])
  const [currentDir, setCurrentDir] = useState('')
  const [openFile, setOpenFile] = useState<OpenWorkspaceFile | null>(null)
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

  // Open the workspace file from the remote server and allow it to be edited ("drafted") which then allows saving it
  // from this client side to the remote server again later.
  async function openWorkspaceFile(entry: WorkspaceFileEntry) {
    if (!session || entry.is_dir) return
    await runPending('file', async () => {
      const file = await readWorkspaceFile(session, entry.path)
      setOpenFile({ ...file, draft: file.content })
    })
  }

  // Update a file that the user is editing.
  function updateUsersDraftForFile(draft: string) {
    setOpenFile((current) => current ? { ...current, draft } : current)
  }

  // Save the users edits/file edits(see above) as a file on the remote file
  async function saveWorkspaceFile() {
    if (!session || !openFile) return
    await runPending('save', async () => {
      const saved = await writeWorkspaceFile(session, {
        content: openFile.draft,
        etag: openFile.etag, // just necessary for the API really and consistency checks
        path: openFile.path,
      })
      setOpenFile({
        content: openFile.draft,
        draft: openFile.draft,
        etag: saved.etag,
        path: saved.path,
      })
      appendMessage('status', `${saved.path} saved.`)
    })
  }

  function refreshFiles() {
    if (session) void loadFiles(session, currentDir)
  }

  const dirtyFile = Boolean(openFile && openFile.draft !== openFile.content)

  return {
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
  }
}
