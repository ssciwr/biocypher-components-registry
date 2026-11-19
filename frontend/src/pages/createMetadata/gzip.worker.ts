import { createGzipSample, type GzipLogicalFormat } from './gzipSampling'

type GzipSampleRequest = { id: string; file: File; format: GzipLogicalFormat }

self.onmessage = async (event: MessageEvent<GzipSampleRequest>) => {
  const { file, format, id } = event.data
  try {
    const artifact = await createGzipSample(file, format)
    const buffer = await artifact.arrayBuffer()
    self.postMessage({ id, artifact: buffer }, { transfer: [buffer] })
  } catch (error) {
    self.postMessage({ id, error: error instanceof Error ? error.message : String(error) })
  }
}
