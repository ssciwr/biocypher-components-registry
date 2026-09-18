import type {
  FileContentResponse,
  FileEntryResponse,
  SessionCreateResponse,
  ToolDescriptor,
} from '../../api/workspace'

export type WorkspaceTool = ToolDescriptor

export type WorkspaceSession = SessionCreateResponse

export type WorkspaceFileEntry = FileEntryResponse

export type WorkspaceFile = FileContentResponse

export type WorkspaceEvent = Readonly<{
  data: unknown
  event: string
  id: string | null
}>

export type WorkspaceViewSession = Readonly<{
  busy: boolean
  error: string | null
  hasLLMKey: boolean
  id: string
  token: string
  tools: WorkspaceTool[]
}>

export type WorkspaceMessage = Readonly<{
  details: string | null
  id: string
  kind: 'assistant' | 'error' | 'status' | 'tool' | 'user'
  text: string
}>

export type PendingAction = 'idle' | 'key' | 'message' | 'session' | 'file'

export type WorkspaceFileAction = (entry: WorkspaceFileEntry) => void
