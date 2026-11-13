import Papa from 'papaparse'

const MAX_DECOMPRESSED_SCAN_BYTES = 8 * 1024 * 1024
const MAX_GZIP_ARTIFACT_BYTES = 1 * 1024 * 1024
const SAMPLE_TARGET_BYTES = 768 * 1024

export type GzipLogicalFormat = 'csv' | 'tsv'

export async function createGzipSample(
  file: File,
  format: GzipLogicalFormat,
): Promise<Blob> {
  if (typeof DecompressionStream === 'undefined' || typeof CompressionStream === 'undefined') {
    throw new TypeError('This browser cannot safely process Gzip datasets. Use the CLI.')
  }

  const { text, truncated } = await readBoundedGzipText(file)
  const delimiter = format === 'csv' ? ',' : '\t'
  const parsed = Papa.parse<string[]>(text, { delimiter, skipEmptyLines: false })
  const rows = [...parsed.data]
  const hasTrailingEmptyRow = /\r?\n$/.test(text)
    && rows.at(-1)?.every((value) => value === '')
  if (truncated || hasTrailingEmptyRow) {
    // Drop either the incomplete final row from a bounded scan or Papa Parse's
    // additional empty row for a conventional trailing line terminator.
    rows.pop()
  }

  const lines: string[] = []
  let bytes = 0
  const encoder = new TextEncoder()
  for (const row of rows) {
    const line = Papa.unparse([row], { delimiter, newline: '\n' }) + '\n'
    const size = encoder.encode(line).byteLength
    if (bytes + size > SAMPLE_TARGET_BYTES) break
    lines.push(line)
    bytes += size
  }
  if (!lines.length) {
    throw new Error('A logical CSV/TSV row exceeds the browser sampling budget. Use the CLI.')
  }

  const plainSample = new Blob(lines, { type: mediaType(format) })
  const compressed = await new Response(
    plainSample.stream().pipeThrough(new CompressionStream('gzip')),
  ).blob()
  if (compressed.size > MAX_GZIP_ARTIFACT_BYTES) {
    throw new Error('The compressed browser sample exceeds 1 MiB. Use the CLI.')
  }
  return compressed
}

async function readBoundedGzipText(file: File): Promise<{ text: string; truncated: boolean }> {
  const reader = file.stream().pipeThrough(new DecompressionStream('gzip')).getReader()
  const decoder = new TextDecoder('utf-8', { fatal: true })
  const parts: string[] = []
  let bytes = 0
  let truncated = false
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const remaining = MAX_DECOMPRESSED_SCAN_BYTES - bytes
      if (value.byteLength > remaining) {
        if (remaining > 0) parts.push(decoder.decode(value.subarray(0, remaining), { stream: true }))
        truncated = true
        await reader.cancel()
        break
      }
      parts.push(decoder.decode(value, { stream: true }))
      bytes += value.byteLength
      if (bytes === MAX_DECOMPRESSED_SCAN_BYTES) {
        truncated = true
        await reader.cancel()
        break
      }
    }
    if (!truncated) parts.push(decoder.decode())
  } catch (error) {
    throw new Error(
      `The selected Gzip file could not be decompressed as UTF-8 ${formatName(file.name)}: ${error instanceof Error ? error.message : String(error)}`,
      { cause: error },
    )
  } finally {
    reader.releaseLock()
  }
  return { text: parts.join(''), truncated }
}

function mediaType(format: GzipLogicalFormat) {
  return format === 'csv' ? 'text/csv' : 'text/tab-separated-values'
}

function formatName(name: string) {
  return name.toLowerCase().endsWith('.csv.gz') ? 'CSV' : 'TSV'
}
