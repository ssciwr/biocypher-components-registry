import type { DatasetDraft } from './types'
import {
  generateDatasetFromSelection,
  type DatasetCapacityWait,
  type DatasetUploadResult,
} from './datasetUpload'
import { datasetUIStateDraftFromCroissantFile } from './utils'

type GenerateDataset = (
  dataset: DatasetDraft,
  options: { onCapacityWait?: (wait: DatasetCapacityWait | null) => void },
) => Promise<DatasetUploadResult>

export type PreparedDatasets = {
  datasets: DatasetDraft[]
  warnings: string[]
}

export async function prepareDatasetDrafts(
  sourceDatasets: DatasetDraft[],
  onCapacityWait: (wait: DatasetCapacityWait | null) => void,
  generateDataset: GenerateDataset = generateDatasetFromSelection,
  index = 0,
  prepared?: PreparedDatasets,
): Promise<PreparedDatasets> {
  const accumulator = prepared ?? { datasets: [], warnings: [] }
  const dataset = sourceDatasets[index]
  if (!dataset) return accumulator

  if (dataset.uploadedDocument) {
    accumulator.datasets.push(dataset)
  } else {
    if (!dataset.sourceSelection) {
      throw new Error('Select a source dataset file or folder first.')
    }
    const result = await generateDataset(dataset, { onCapacityWait })
    accumulator.warnings.push(...result.warnings)
    accumulator.datasets.push(datasetUIStateDraftFromCroissantFile(result.metadata, dataset))
  }

  return prepareDatasetDrafts(
    sourceDatasets,
    onCapacityWait,
    generateDataset,
    index + 1,
    accumulator,
  )
}
