import { createSHA256 } from 'hash-wasm'

type HashRequest = { id: string; blob: Blob; validateUtf8: boolean }

self.onmessage = async (event: MessageEvent<HashRequest>) => {
  const { blob, id, validateUtf8 } = event.data
  try {
    const hasher = await createSHA256()
    hasher.init()
    const decoder = validateUtf8 ? new TextDecoder('utf-8', { fatal: true }) : null
    const reader = blob.stream().getReader()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      hasher.update(value)
      decoder?.decode(value, { stream: true })
    }
    decoder?.decode()
    self.postMessage({ id, sha256: hasher.digest('hex') })
  } catch (error) {
    self.postMessage({ id, error: error instanceof Error ? error.message : String(error) })
  }
}
