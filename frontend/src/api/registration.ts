import {
  streamRegistrationApiV1RegistrationsStreamPost,
  type RegistrationAttemptResponse,
  type RegistrationCreateRequest,
  type RegistrationStreamEvent,
  type ValidationCheckResponse,
} from './client'

const unconfirmedMessage = 'The connection ended before a final registration result arrived. Check the adapter list before trying again.'

export class RegistrationRequestRejectedError extends Error {}

export async function submitRegistrationStream(
  body: RegistrationCreateRequest,
  signal: AbortSignal,
  onChecks: (checks: ValidationCheckResponse[]) => void,
): Promise<RegistrationAttemptResponse> {
  let checks: ValidationCheckResponse[] = []
  let result: RegistrationAttemptResponse | undefined
  let terminalError: Error | undefined
  const { stream } = await streamRegistrationApiV1RegistrationsStreamPost({
    body,
    signal,
    // One initial request and zero retries: reconnecting would submit again.
    sseMaxRetryAttempts: 1,
    fetch: async (request) => {
      const response = await fetch(request)
      if (!response.ok && response.status < 500) {
        const payload = await response.clone().json().catch(() => null) as { detail?: unknown } | null
        terminalError = new RegistrationRequestRejectedError(typeof payload?.detail === 'string' ? payload.detail : `Registration request rejected (${response.status}).`)
      }
      return response
    },
    onSseEvent: ({ data }) => {
      // Heartbeat comments have no data; the generated client also invokes this hook for them.
      const event = data as RegistrationStreamEvent | undefined
      if (!event || result || terminalError || signal.aborted) return
      if (event.type === 'snapshot') checks = event.checks ?? []
      else if (event.type === 'check' && event.check) {
        const update = event.check
        checks = checks.some(check => check.id === update.id)
          ? checks.map(check => check.id === update.id ? update : check)
          : [...checks, update]
      } else if (event.type === 'result' && event.result) result = event.result
      else if (event.type === 'error') {
        terminalError = event.status_code && event.status_code < 500
          ? new RegistrationRequestRejectedError(event.detail ?? 'Registration request rejected.')
          : new Error(`${event.detail ?? 'Processing stopped.'} ${unconfirmedMessage}`)
      }
      onChecks(checks)
    },
  })

  const iterator = stream[Symbol.asyncIterator]()
  try {
    while (!(await iterator.next()).done) {
      if (result || terminalError) break
    }
  } finally {
    await iterator.return()
  }
  if (terminalError) throw terminalError
  if (!result) throw new Error(unconfirmedMessage)
  return result
}
