import Papa, { type ParseResult } from 'papaparse'
import type { DatasetDraft } from './types'
import { creatorToApiValue, optionalValue } from './utils'

const MAX_FILES = 1_000
const MAX_ARTIFACT_BYTES = 1 * 1024 * 1024
const MAX_SESSION_ARTIFACT_BYTES = 50 * 1024 * 1024
const SAMPLE_TARGET_BYTES = 768 * 1024

type LogicalFormat = 'csv' | 'tsv'
type Compression = 'gzip' | undefined
type InventoryEntry = {
  entry_id: string
  relative_path: string
  original_size: number
  logical_format: LogicalFormat
  compression?: 'gzip'
  artifact_mode: 'complete' | 'sample'
  strategy: string
  artifact_size: number
  content_url?: string
}
type PreparedEntry = {
  artifact: Blob
  entry: InventoryEntry
  file: File
  originalSha256: string
}
type SessionResponse = { kind: 'session'; session_id: string; token: string }
type SessionStatus = {
  status: string
  next_poll_ms: number
  result?: DatasetUploadResult
  error?: string
}
export type DatasetUploadResult = {
  metadata: Record<string, unknown>
  warnings: string[]
}

export type DatasetCapacityWait = {
  retryAfterSeconds: number
  attempt: number
  isRetrying: boolean
  retryNow: () => void
  cancel: () => void
}

type DatasetUploadOptions = {
  onCapacityWait?: (wait: DatasetCapacityWait | null) => void
}

class DatasetCapacityError extends Error {
  readonly retryAfterSeconds: number

  constructor(retryAfterSeconds: number) {
    super('Generation capacity is currently full.')
    this.retryAfterSeconds = retryAfterSeconds
  }
}

export class DatasetCapacityCancelledError extends Error {}

export async function generateDatasetFromSelection(
  dataset: DatasetDraft,
  options: DatasetUploadOptions = {},
): Promise<DatasetUploadResult> {
  const selection = dataset.sourceSelection
  if (!selection) throw new Error('Select a source dataset file or folder first.')
  if (!dataset.creators.length) throw new Error('Add at least one dataset creator.')
  if (selection.entries.length > MAX_FILES) {
    throw new Error(`A folder may contain at most ${MAX_FILES} files.`)
  }

  const plans = selection.entries.map((source, index) => (
    planEntry(source.file, source.relativePath, index, selection.kind, dataset)
  ))
  assertSafeInventory(plans.map((plan) => plan.entry))
  // Finish all local work before consuming scarce server admission capacity.
  // Prepared artifacts remain only in browser memory until the session exists.
  const preparedEntries = await prepareEntries(plans)
  const admissionRequest: RequestInit = {
    method: 'POST',
    body: JSON.stringify({
      source_kind: selection.kind,
      source_name: selection.name,
      entries: preparedEntries.map((prepared) => prepared.entry),
      generation: {
        generator: 'auto',
        validate: true,
        name: optionalValue(dataset.name),
        description: optionalValue(dataset.description),
        url: optionalValue(dataset.url),
        license: optionalValue(dataset.license),
        citation: optionalValue(dataset.citation),
        dataset_version: optionalValue(dataset.datasetVersion),
        date_published: optionalValue(dataset.datePublished),
        creators: dataset.creators.map(creatorToApiValue),
      },
    }),
    headers: { 'Content-Type': 'application/json' },
  }
  const admission = await requestAdmissionWithRetry(admissionRequest, options)
  const session = admission

  try {
    await uploadPreparedEntries(session, preparedEntries)
    await requestJson<{ status: string }>(
      `/api/v1/metadata/upload-sessions/${encodeURIComponent(session.session_id)}/finalize`,
      { method: 'POST', headers: { Authorization: `Bearer ${session.token}` } },
    )
    return await waitForGeneration(session)
  } catch (error) {
    await fetch(`/api/v1/metadata/upload-sessions/${encodeURIComponent(session.session_id)}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${session.token}` },
      cache: 'no-store',
    }).catch(() => undefined)
    throw error
  }
}

export async function requestAdmissionWithRetry(
  request: RequestInit,
  options: DatasetUploadOptions,
): Promise<SessionResponse> {
  return requestAdmissionAttempt(request, options, 1)
}

async function requestAdmissionAttempt(
  request: RequestInit,
  options: DatasetUploadOptions,
  attempt: number,
): Promise<SessionResponse> {
  try {
    const admission = await requestJson<SessionResponse>(
      '/api/v1/metadata/upload-sessions',
      request,
    )
    options.onCapacityWait?.(null)
    return admission
  } catch (error) {
    if (!(error instanceof DatasetCapacityError)) throw error
    await waitForCapacityRetry(error.retryAfterSeconds, attempt, options)
    return requestAdmissionAttempt(request, options, attempt + 1)
  }
}

function waitForCapacityRetry(
  retryAfterSeconds: number,
  attempt: number,
  options: DatasetUploadOptions,
): Promise<void> {
  return new Promise((resolve, reject) => {
    let settled = false
    const finish = (action: 'retry' | 'cancel') => {
      if (settled) return
      settled = true
      globalThis.clearTimeout(timer)
      if (action === 'retry') {
        options.onCapacityWait?.({
          retryAfterSeconds,
          attempt,
          isRetrying: true,
          retryNow: () => undefined,
          cancel: () => undefined,
        })
        resolve()
      } else {
        options.onCapacityWait?.(null)
        reject(new DatasetCapacityCancelledError('Generation retry was cancelled.'))
      }
    }
    const timer = globalThis.setTimeout(() => finish('retry'), retryAfterSeconds * 1_000)
    options.onCapacityWait?.({
      retryAfterSeconds,
      attempt,
      isRetrying: false,
      retryNow: () => finish('retry'),
      cancel: () => finish('cancel'),
    })
  })
}

export async function waitForGeneration(session: SessionResponse): Promise<DatasetUploadResult> {
  let delay = 1_000
  while (true) {
    await wait(delay)
    const status = await requestJson<SessionStatus>(
      `/api/v1/metadata/upload-sessions/${encodeURIComponent(session.session_id)}`,
      { headers: { Authorization: `Bearer ${session.token}` } },
    )
    if (status.status === 'complete' && status.result) return status.result
    if (status.status === 'failed') throw new Error(status.error || 'Dataset generation failed.')
    delay = status.next_poll_ms
  }
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => globalThis.setTimeout(resolve, milliseconds))
}

function planEntry(
  file: File,
  selectedPath: string,
  index: number,
  kind: 'file' | 'folder',
  dataset: DatasetDraft,
): PreparedEntry {
  const relativePath = kind === 'folder' ? selectedPath : file.name
  const { compression, format } = sourceFormat(relativePath)
  const sample = compression === 'gzip' || artifactModeForSize(file.size) === 'sample'
  return {
    artifact: file,
    file,
    originalSha256: '',
    entry: {
      entry_id: `entry-${index + 1}`,
      relative_path: relativePath,
      original_size: file.size,
      logical_format: format,
      compression,
      artifact_mode: sample ? 'sample' : 'complete',
      strategy: artifactStrategy(format, compression, sample),
      artifact_size: 0,
      content_url: kind === 'file' ? optionalValue(dataset.contentUrl) : undefined,
    },
  }
}

function artifactStrategy(format: LogicalFormat, compression: Compression, sample: boolean) {
  if (compression === 'gzip') return `${format}-gzip-complete-rows-v1`
  if (sample) return `${format}-complete-rows-v1`
  return 'complete-file-v1'
}

async function prepareEntries(
  plans: PreparedEntry[],
  index = 0,
  preparedEntries: PreparedEntry[] = [],
  preparedBytes = 0,
): Promise<PreparedEntry[]> {
  if (index >= plans.length) return preparedEntries

  const prepared = await prepareEntry(plans[index])
  if (prepared.artifact.size > MAX_ARTIFACT_BYTES) {
    throw new Error(`A prepared artifact exceeds ${MAX_ARTIFACT_BYTES} bytes. Use the CLI.`)
  }
  const nextPreparedBytes = preparedBytes + prepared.artifact.size
  if (nextPreparedBytes > MAX_SESSION_ARTIFACT_BYTES) {
    throw new Error('The prepared dataset exceeds the 50 MiB browser upload budget. Use the CLI.')
  }
  prepared.entry.artifact_size = prepared.artifact.size
  preparedEntries.push(prepared)
  return prepareEntries(plans, index + 1, preparedEntries, nextPreparedBytes)
}

async function uploadPreparedEntries(
  session: SessionResponse,
  preparedEntries: PreparedEntry[],
  index = 0,
): Promise<void> {
  const prepared = preparedEntries[index]
  if (!prepared) return

  const artifactSha256 = await hashBlob(prepared.artifact, false)
  await requestJson(
    `/api/v1/metadata/upload-sessions/${encodeURIComponent(session.session_id)}/artifacts/${encodeURIComponent(prepared.entry.entry_id)}`,
    {
      method: 'PUT',
      body: prepared.artifact,
      headers: {
        Authorization: `Bearer ${session.token}`,
        'Content-Type': 'application/octet-stream',
        'X-Artifact-SHA256': artifactSha256,
        'X-Original-SHA256': prepared.originalSha256,
      },
    },
  )
  return uploadPreparedEntries(session, preparedEntries, index + 1)
}

async function prepareEntry(plan: PreparedEntry): Promise<PreparedEntry> {
  const originalSha256 = await hashBlob(plan.file, plan.entry.compression !== 'gzip')
  let artifact = plan.file as Blob
  if (plan.entry.compression === 'gzip') {
    artifact = await sampleGzipInWorker(plan.file, plan.entry.logical_format)
  } else if (plan.entry.artifact_mode === 'sample') {
    artifact = await sampleDelimitedFile(plan.file, plan.entry.logical_format)
  }
  return { ...plan, artifact, originalSha256 }
}

function sampleGzipInWorker(file: File, format: LogicalFormat): Promise<Blob> {
  const worker = new Worker(new URL('./gzip.worker.ts', import.meta.url), { type: 'module' })
  const id = crypto.randomUUID()
  return new Promise((resolve, reject) => {
    worker.onmessage = (event: MessageEvent<{ id: string; artifact?: ArrayBuffer; error?: string }>) => {
      if (event.data.id !== id) return
      worker.terminate()
      if (event.data.error || !event.data.artifact) {
        reject(new Error(event.data.error || 'The Gzip sample worker returned no artifact.'))
      } else {
        resolve(new Blob([event.data.artifact], { type: 'application/gzip' }))
      }
    }
    worker.onerror = (event) => {
      worker.terminate()
      reject(new Error(event.message))
    }
    worker.postMessage({ id, file, format })
  })
}

function hashBlob(blob: Blob, validateUtf8: boolean): Promise<string> {
  const worker = new Worker(new URL('./hash.worker.ts', import.meta.url), { type: 'module' })
  const id = crypto.randomUUID()
  return new Promise((resolve, reject) => {
    worker.onmessage = (event: MessageEvent<{ id: string; sha256?: string; error?: string }>) => {
      if (event.data.id !== id) return
      worker.terminate()
      if (event.data.error) {
        reject(new Error(`The selected file is not valid UTF-8: ${event.data.error}`))
      } else {
        resolve(event.data.sha256 ?? '')
      }
    }
    worker.onerror = (event) => {
      worker.terminate()
      reject(new Error(event.message))
    }
    worker.postMessage({ id, blob, validateUtf8 })
  })
}

function sampleDelimitedFile(file: File, format: LogicalFormat): Promise<Blob> {
  const delimiter = format === 'csv' ? ',' : '\t'
  return new Promise((resolve, reject) => {
    const lines: string[] = []
    let bytes = 0
    Papa.parse<string[]>(file, {
      delimiter,
      skipEmptyLines: false,
      chunk(results: ParseResult<string[]>, parser) {
        for (const row of results.data) {
          const line = serializeDelimitedRow(row, delimiter)
          const size = new TextEncoder().encode(line).byteLength
          if (bytes + size > SAMPLE_TARGET_BYTES) {
            parser.abort()
            if (!lines.length) {
              reject(new Error('A logical CSV/TSV row exceeds the browser sampling budget. Use the CLI.'))
              return
            }
            resolve(new Blob(lines, { type: mediaType(format) }))
            return
          }
          lines.push(line)
          bytes += size
        }
      },
      complete() {
        resolve(new Blob(lines, { type: mediaType(format) }))
      },
      error(error) { reject(error) },
    })
  })
}

export function serializeDelimitedRow(row: string[], delimiter: ',' | '\t') {
  return Papa.unparse([row], { delimiter, newline: '\n' }) + '\n'
}

export function artifactModeForSize(size: number): 'complete' | 'sample' {
  return size > MAX_ARTIFACT_BYTES ? 'sample' : 'complete'
}

function mediaType(format: LogicalFormat) {
  return format === 'csv' ? 'text/csv' : 'text/tab-separated-values'
}

export function sourceFormat(path: string): { format: LogicalFormat; compression: Compression } {
  const lower = path.toLowerCase()
  if (lower.endsWith('.csv.gz')) return { format: 'csv', compression: 'gzip' }
  if (lower.endsWith('.tsv.gz')) return { format: 'tsv', compression: 'gzip' }
  if (lower.endsWith('.csv')) return { format: 'csv', compression: undefined }
  if (lower.endsWith('.tsv')) return { format: 'tsv', compression: undefined }
  throw new Error(`Unsupported file '${path}'. Use UTF-8 CSV/TSV, optionally Gzip-compressed, or the CLI.`)
}

function assertSafeInventory(entries: InventoryEntry[]) {
  const seen = new Set<string>()
  for (const entry of entries) {
    const path = entry.relative_path.normalize('NFC')
    if (
      !path || path.startsWith('/') || path.includes('\\')
      || path.split('/').some((part) => !part || part === '.' || part === '..')
      || hasControlCharacter(path)
    ) {
      throw new Error(`Unsafe dataset path '${entry.relative_path}'.`)
    }
    const identity = path.toLocaleLowerCase()
    if (seen.has(identity)) throw new Error(`Dataset path collision '${path}'.`)
    seen.add(identity)
    entry.relative_path = path
  }
}

function hasControlCharacter(value: string) {
  return Array.from(value).some((character) => {
    const codePoint = character.codePointAt(0) ?? 0
    return codePoint <= 31 || codePoint === 127
  })
}

async function requestJson<T>(url: string, init: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: 'no-store' })
  const body = await response.json().catch(() => ({})) as { detail?: unknown }
  if (!response.ok) {
    if (response.status === 429) {
      const retryAfter = Number.parseInt(response.headers.get('Retry-After') || '15', 10)
      throw new DatasetCapacityError(Number.isFinite(retryAfter) ? retryAfter : 15)
    }
    const detail = typeof body.detail === 'string'
      ? body.detail
      : `Request failed with status ${response.status}.`
    throw new Error(detail)
  }
  return body as T
}
