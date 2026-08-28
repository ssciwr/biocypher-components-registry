/*
 * Priority is to make it so we can interact with SSE functions over OpenAPI-TS
 * types without knowing the intricacies of what repeated JSON structures need
 * to be sent (e.g. If-Match as a header). This is largely a consequence of
 * OpenAPI-TS being oriented towards simpler HTTP calls whereas SSE has more
 * complexity and a little more boilerplate.
 */
import {
  createSessionAgentApiV1SessionsPost,
  eventsAgentApiV1SessionsSessionIdEventsGet,
  interruptAgentApiV1SessionsSessionIdInterruptPost,
  listFilesAgentApiV1SessionsSessionIdFilesGet,
  postMessageAgentApiV1SessionsSessionIdMessagesPost,
  readFileAgentApiV1SessionsSessionIdFileGet,
  setKeyAgentApiV1SessionsSessionIdKeyPost,
  writeFileAgentApiV1SessionsSessionIdFilePut,
} from '../../api/workspace'
import type { StreamEvent } from '../../api/workspace/core/serverSentEvents.gen'
import type {
  WorkspaceFile,
  WorkspaceSession,
  WorkspaceViewSession,
} from './types'

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

export async function consumeWorkspaceEvents(
  session: WorkspaceAccess,
  options: WorkspaceEventsOptions,
) {
  const { stream } = await eventsAgentApiV1SessionsSessionIdEventsGet({
    ...sessionOptions(session),
    onSseError: options.onError,
    onSseEvent: options.onEvent,
    signal: options.signal,
    sseMaxRetryAttempts: 0,
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

export async function attachWorkspaceKey(session: WorkspaceAccess, apiKey: string) {
  await setKeyAgentApiV1SessionsSessionIdKeyPost({
    ...sessionOptions(session),
    body: { api_key: apiKey }, // Frontend only uses api_key, not auth_token, so we could remove auth_token
  }) // todo: Remove auth_token (PR comment mentioned this as a separate issue).
  // This is the BYOK key nor our key.
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

export async function writeWorkspaceFile(
  session: WorkspaceAccess,
  file: WorkspaceFile,
) {
  const options = sessionOptions(session)
  const { data } = await writeFileAgentApiV1SessionsSessionIdFilePut({
    ...options,
    body: { content: file.content },
    headers: {
      ...options.headers,
      'If-Match': file.etag,
    },
    query: { path: file.path },
  })
  return data
}
