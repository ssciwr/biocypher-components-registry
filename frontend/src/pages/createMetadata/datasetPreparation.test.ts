import { describe, expect, it, vi } from 'vitest'
import { emptyDataset } from './options'
import { prepareDatasetDrafts } from './datasetPreparation'
import type { DatasetDraft } from './types'

function generatedDraft(id: string): DatasetDraft {
  const file = new File(['id,name\n1,Alice\n'], `${id}.csv`, { type: 'text/csv' })
  return {
    ...emptyDataset,
    id,
    name: id,
    sourceSelection: {
      entries: [{ file, relativePath: file.name }],
      kind: 'file',
      name: file.name,
    },
  }
}

describe('dataset preparation order', () => {
  it('prepares generated datasets sequentially and preserves their order and warnings', async () => {
    const first = generatedDraft('first')
    const second = generatedDraft('second')
    let activeGenerations = 0
    let maximumActiveGenerations = 0
    const generate = vi.fn(async (dataset: DatasetDraft) => {
      activeGenerations += 1
      maximumActiveGenerations = Math.max(maximumActiveGenerations, activeGenerations)
      await Promise.resolve()
      activeGenerations -= 1
      return {
        metadata: { '@type': 'sc:Dataset', name: dataset.name },
        warnings: [`${dataset.id} warning`],
      }
    })

    const result = await prepareDatasetDrafts([first, second], vi.fn(), generate)

    expect(maximumActiveGenerations).toBe(1)
    expect(generate.mock.calls.map(([dataset]) => dataset.id)).toEqual(['first', 'second'])
    expect(result.datasets.map((dataset) => dataset.name)).toEqual(['first', 'second'])
    expect(result.warnings).toEqual(['first warning', 'second warning'])
  })

  it('keeps uploaded Croissant datasets unchanged and does not generate them again', async () => {
    const uploaded = {
      ...emptyDataset,
      id: 'uploaded',
      mode: 'upload' as const,
      uploadedDocument: { '@type': 'sc:Dataset', name: 'Uploaded' },
    }
    const generate = vi.fn()

    const result = await prepareDatasetDrafts([uploaded], vi.fn(), generate)

    expect(generate).not.toHaveBeenCalled()
    expect(result).toEqual({ datasets: [uploaded], warnings: [] })
    expect(result.datasets[0]).toBe(uploaded)
  })

  it('stops immediately when generation fails', async () => {
    const first = generatedDraft('first')
    const second = generatedDraft('second')
    const failure = new Error('Generation failed')
    const generate = vi.fn().mockRejectedValue(failure)

    await expect(prepareDatasetDrafts([first, second], vi.fn(), generate)).rejects.toBe(failure)
    expect(generate).toHaveBeenCalledTimes(1)
    expect(generate.mock.calls[0]?.[0]).toBe(first)
  })

  it('rejects a generated dataset without a source selection before generation', async () => {
    const generate = vi.fn()

    await expect(prepareDatasetDrafts([
      { ...emptyDataset, id: 'missing-source' },
    ], vi.fn(), generate)).rejects.toThrow('Select a source dataset file or folder first.')
    expect(generate).not.toHaveBeenCalled()
  })
})
