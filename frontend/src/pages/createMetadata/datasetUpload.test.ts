import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  artifactModeForSize,
  generateDatasetFromSelection,
  requestAdmissionWithRetry,
  serializeDelimitedRow,
  sourceFormat,
  waitForGeneration,
} from './datasetUpload'
import { createGzipSample } from './gzipSampling'
import { emptyDataset } from './options'

describe('browser dataset preparation', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('rejects an empty included selection before reading files or contacting the server', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    await expect(generateDatasetFromSelection({ ...emptyDataset, sourceSelection: {
      kind: 'file', name: 'data.csv', entries: [
        { file: new File(['id\n1'], 'data.csv'), relativePath: 'data.csv', excluded: true },
      ],
    } })).rejects.toThrow('Select at least one source file to include.')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('uploads and describes only included files, ignoring excluded unsupported files', async () => {
    vi.useFakeTimers()
    const hashedFiles: string[] = []
    vi.stubGlobal('Worker', class {
      onmessage?: (event: { data: { id: string; sha256: string } }) => void
      postMessage({ id, blob }: { id: string; blob: File }) {
        hashedFiles.push(blob.name)
        this.onmessage?.({ data: { id, sha256: 'a'.repeat(64) } })
      }
      terminate() {}
    })
    const metadata = { name: 'Included dataset' }
    const fetchMock = vi.fn(async (url: string) => new Response(JSON.stringify(
      url === '/api/v1/metadata/upload-sessions'
        ? { kind: 'session', session_id: 'session-1', token: 'token' }
        : url.endsWith('/session-1')
          ? { status: 'complete', result: { metadata, warnings: [] } }
          : { status: 'ok' },
    ), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const pending = generateDatasetFromSelection({ ...emptyDataset,
      creators: [{ id: 'creator', name: 'Example', creatorType: 'Organization', affiliation: '', email: '', orcid: '', url: '' }],
      sourceSelection: { kind: 'folder', name: 'STITCH', entries: [
        { file: new File(['id\n1'], 'actions.tsv'), relativePath: 'nested/actions.tsv' },
        { file: new File(['citation'], 'citation.bibtex'), relativePath: 'citation.bibtex', excluded: true },
      ] },
    })
    await vi.runAllTimersAsync()
    await expect(pending).resolves.toEqual({ metadata, warnings: [] })
    const inventory = JSON.parse((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as string)
    expect(inventory.entries).toHaveLength(1)
    expect(inventory.entries[0].relative_path).toBe('nested/actions.tsv')
    expect(hashedFiles).toEqual(['actions.tsv', 'actions.tsv'])
    expect(fetchMock.mock.calls.filter(([url]) => url.includes('/artifacts/'))).toHaveLength(1)
  })

  it('switches to sampling only above the 1 MiB boundary', () => {
    expect(artifactModeForSize(1 * 1024 * 1024)).toBe('complete')
    expect(artifactModeForSize(1 * 1024 * 1024 + 1)).toBe('sample')
  })

  it('serializes quoted delimiters and multiline values as one logical CSV row', () => {
    expect(serializeDelimitedRow(['1', 'Smith, Alice', 'first\nsecond'], ',')).toBe(
      '1,"Smith, Alice","first\nsecond"\n',
    )
  })

  it('serializes embedded tabs and multiline values as one logical TSV row', () => {
    expect(serializeDelimitedRow(['1', 'left\tright', 'first\nsecond'], '\t')).toBe(
      '1\t"left\tright"\t"first\nsecond"\n',
    )
  })

  it('recognizes Baker-compatible Gzip wrappers', () => {
    expect(sourceFormat('people.csv.gz')).toEqual({ format: 'csv', compression: 'gzip' })
    expect(sourceFormat('nested/people.tsv.gz')).toEqual({ format: 'tsv', compression: 'gzip' })
  })

  it('decompresses, samples, and recompresses a TSV for Baker', async () => {
    const source = 'id\tnote\n1\t"first\nsecond"\n2\tdone\n'
    const compressed = await new Response(
      new Blob([source]).stream().pipeThrough(new CompressionStream('gzip')),
    ).arrayBuffer()
    const file = new File([compressed], 'people.tsv.gz', { type: 'application/gzip' })

    const sample = await createGzipSample(file, 'tsv')
    const restored = await new Response(
      sample.stream().pipeThrough(new DecompressionStream('gzip')),
    ).text()

    expect(sample.type).toBe('')
    expect(restored).toBe(source)
  })

  it('polls asynchronous generation until the terminal result is available', async () => {
    vi.useFakeTimers()
    const result = { metadata: { name: 'Dataset' }, warnings: [] }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        status: 'processing', next_poll_ms: 5,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        status: 'complete', next_poll_ms: 5, result,
      }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const pending = waitForGeneration({
      kind: 'session', session_id: 'session-1', token: 'session-token',
    })
    await vi.runAllTimersAsync()

    await expect(pending).resolves.toEqual(result)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('retries only admission and reuses the prepared request after capacity is full', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Queue full' }), {
        status: 429,
        headers: { 'Retry-After': '15', 'Content-Type': 'application/json' },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        kind: 'session', session_id: 'session-1', token: 'session-token',
      }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    let retryNow: (() => void) | undefined
    const capacityStates: Array<{ attempt: number; isRetrying: boolean } | null> = []
    const request = { method: 'POST', body: 'prepared-request' }

    const pending = requestAdmissionWithRetry(request, {
      onCapacityWait: (wait) => {
        retryNow = wait?.retryNow
        capacityStates.push(wait ? {
          attempt: wait.attempt,
          isRetrying: wait.isRetrying,
        } : null)
      },
    })
    await vi.waitFor(() => expect(retryNow).toBeTypeOf('function'))
    retryNow?.()

    await expect(pending).resolves.toMatchObject({ session_id: 'session-1' })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0]?.[1]?.body).toBe('prepared-request')
    expect(fetchMock.mock.calls[1]?.[1]?.body).toBe('prepared-request')
    expect(capacityStates).toEqual([
      { attempt: 1, isRetrying: false },
      { attempt: 1, isRetrying: true },
      null,
    ])
  })
})
