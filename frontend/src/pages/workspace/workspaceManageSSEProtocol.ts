/*
 * Priority is to make it so we can interact with SSE functions over OpenAPI-TS
 * types without knowing the intricacies of repeated request structures.
 *
 *  This is largely a consequence of
 * OpenAPI-TS being oriented towards simpler HTTP calls whereas SSE has more
 * complexity and a little more boilerplate.
 */
import {
  createSessionAgentApiV1SessionsPost,
  deleteSessionAgentApiV1SessionsSessionIdDelete,
  downloadFilesAgentApiV1SessionsSessionIdDownloadGet,
  eventsAgentApiV1SessionsSessionIdEventsGet,
  getSessionAgentApiV1SessionsSessionIdGet,
  interruptAgentApiV1SessionsSessionIdInterruptPost,
  listFilesAgentApiV1SessionsSessionIdFilesGet,
  postMessageAgentApiV1SessionsSessionIdMessagesPost,
  readFileAgentApiV1SessionsSessionIdFileGet,
  setKeyAgentApiV1SessionsSessionIdKeyPost,
} from '../../api/workspace'
import type { StreamEvent } from '../../api/workspace/core/serverSentEvents.gen'
import type {
  WorkspaceFile,
  WorkspaceSession,
  WorkspaceViewSession,
} from './types'
import type { SessionStateResponse } from '../../api/workspace'

type WorkspaceAccess = Pick<WorkspaceViewSession, 'id' | 'token'>

type WorkspaceEventsOptions = Readonly<{
  onError: (error: unknown) => void
  onEvent: (event: StreamEvent<unknown>) => void
  signal: AbortSignal
}>

type WorkspaceSessionOptions = Readonly<{
  headers: Readonly<{ authorization: string }>
  path: Readonly<{ session_id: string }>
  throwOnError: true
}>

export function workspaceErrorMessage(error: unknown) {
  if (typeof error === 'object' && error !== null) {
    const detail = (error as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
  }
  return error instanceof Error ? error.message : 'Workspace request failed.'
}

function sessionOptions(session: WorkspaceAccess): WorkspaceSessionOptions {
  return {
    headers: { authorization: `Bearer ${session.token}` },
    path: { session_id: session.id },
    throwOnError: true,
  }
}

export async function createWorkspaceSession(): Promise<WorkspaceSession> {
  const { data } = await createSessionAgentApiV1SessionsPost({
    throwOnError: true,
  })
  return data
}

export async function getWorkspaceSessionState(
  session: WorkspaceAccess,
): Promise<SessionStateResponse> {
  const { data } = await getSessionAgentApiV1SessionsSessionIdGet(sessionOptions(session))
  return data
}

export async function consumeWorkspaceEvents(
  session: WorkspaceAccess,
  options: WorkspaceEventsOptions,
) {
  const { stream } = await eventsAgentApiV1SessionsSessionIdEventsGet({
    ...sessionOptions(session),
    onSseError: options.onError,
    onSseEvent: options.onEvent,
    signal: options.signal,
    sseMaxRetryAttempts: 5,
  })

  // This looks odd, but the openapi-ts SSE client is a "lazy" generated. Consuming the stream events makes onSseEvent fire as expected.
  const streamIterator = stream[Symbol.asyncIterator]()
  let streamResult = await streamIterator.next()

  while (!streamResult.done) {
    streamResult = await streamIterator.next()
  }
}

export async function listWorkspaceFiles(session: WorkspaceAccess, path = '') {
  const { data } = await listFilesAgentApiV1SessionsSessionIdFilesGet({
    ...sessionOptions(session),
    query: { path },
  })
  return data
}

export async function downloadWorkspaceFiles(session: WorkspaceAccess): Promise<void> {
  const { data } = await downloadFilesAgentApiV1SessionsSessionIdDownloadGet({
    ...sessionOptions(session),
    parseAs: 'blob',
  })
  const downloadUrl = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.download = 'workspace.zip'
  link.href = downloadUrl
  link.click()
  URL.revokeObjectURL(downloadUrl)
}

export async function attachWorkspaceKey(session: WorkspaceAccess, apiKey: string) {
  await setKeyAgentApiV1SessionsSessionIdKeyPost({
    ...sessionOptions(session),
    body: { api_key: apiKey },
  })
  // This is the BYOK key nor our key.
}

export async function endWorkspaceSession(session: WorkspaceAccess) {
  await deleteSessionAgentApiV1SessionsSessionIdDelete({
    ...sessionOptions(session),
    keepalive: true,
  })
}

export async function sendWorkspaceMessage(
  session: WorkspaceAccess,
  content: string,
) {
  await postMessageAgentApiV1SessionsSessionIdMessagesPost({
    ...sessionOptions(session),
    body: { content },
  })
}

export async function interruptWorkspaceTurn(session: WorkspaceAccess) {
  await interruptAgentApiV1SessionsSessionIdInterruptPost(sessionOptions(session))
}

export async function readWorkspaceFile(
  session: WorkspaceAccess,
  path: string,
): Promise<WorkspaceFile> {
  const { data } = await readFileAgentApiV1SessionsSessionIdFileGet({
    ...sessionOptions(session),
    query: { path },
  })
  return data
}
