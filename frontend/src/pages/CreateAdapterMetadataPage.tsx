import { useEffect, useState, type FormEvent } from 'react'
import { ArrowDownTrayIcon } from '@heroicons/react/24/outline'
import {
  generateAdapterMetadataApiV1MetadataAdaptersGeneratePost,
  generateDatasetMetadataApiV1MetadataDatasetsGeneratePost,
} from '../api/client'
import {
  AdapterDetailsStep,
  DatasetBasicsStep,
  DatasetDetailsStep,
} from './createMetadata/MetadataGeneratorSteps'
import { emptyCreator, emptyDataset, emptyForm } from './createMetadata/options'
import type {
  CreatorDraft,
  DatasetDraft,
  DatasetDatasetManualField,
  DatasetMode,
  MetadataGeneratorForm,
  MetadataStep,
} from './createMetadata/types'
import {
  creatorToApiValue,
  datasetUIStateDraftFromCroissantFile,
  datasetDraftToDocument,
  datasetDraftToCroissantGenerateUploadForm,
  downloadMetadata,
  emptyDatasetManualField,
  errorText,
  keywordsToApiValues,
  nextDraftId,
  optionalValue,
} from './createMetadata/utils'
import { metadataDraftStorageKey } from './createMetadata/storage'

const steps: ReadonlyArray<{ label: string; step: MetadataStep }> = [
  { label: 'Basic info adapter', step: 1 },
  { label: 'Basic info datasets', step: 2 },
  { label: 'Dataset(s) details', step: 3 },
  { label: 'Validate & Download', step: 4 },
]

// Steps UI like in the adapter registration page vertical format, on the right
function Stepper({ currentStep }: Readonly<{ currentStep: MetadataStep }>) {
  return (
    <nav
      aria-label="Metadata generator progress"
      className="hidden rounded-2xl border-2 border-slate-300 bg-white p-5 shadow-md lg:sticky lg:top-24 lg:block"
    >
      <ol className="grid gap-0">
        {steps.map((item, index) => {
          const isComplete = item.step < currentStep
          const isCurrent = item.step === currentStep
          const hasNextStep = index < steps.length - 1
          let markerClass = 'border-slate-300 bg-white text-slate-500'
          let labelClass = 'text-slate-500'
          let lineClass = 'bg-slate-300'
          let statusText = 'Not started'

          if (isComplete) {
            markerClass = 'border-slate-950 bg-slate-950 text-white'
            labelClass = 'text-slate-950'
            statusText = 'Complete'
          }
          if (isCurrent) {
            markerClass = 'border-slate-950 bg-slate-950 text-white'
            labelClass = 'text-slate-950'
            lineClass = 'bg-slate-950'
            statusText = 'Current step'
          }

          return (
            <li className="relative grid grid-cols-[2.5rem_minmax(0,1fr)] gap-3 pb-6 last:pb-0" key={item.step}>
              {hasNextStep ? (
                <span className={`absolute left-5 top-10 h-[calc(100%-2.5rem)] w-0.5 ${lineClass}`} aria-hidden="true" />
              ) : null}
              <span
                aria-current={isCurrent ? 'step' : undefined}
                className={`relative z-10 flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-bold ${markerClass}`}
              >
                {item.step}
              </span>
              <span className="pt-0.5">
                <span className={`block text-sm font-semibold leading-5 ${labelClass}`}>
                  {item.label}
                </span>
                <span className="mt-1 block text-xs text-slate-500">
                  {statusText}
                </span>
              </span>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

// Use local storage for the latest draft (we only ever keep one draft)
function restoreStoredDataset(dataset: Partial<DatasetDraft>): DatasetDraft {
  let mode: DatasetMode = 'generate'
  if (dataset.mode === 'upload') {
    mode = 'upload'
  }

  return {
    ...emptyDataset,
    ...dataset,
    creators: Array.isArray(dataset.creators) ? dataset.creators : [], // is Array usei s for safety overwriting to avoid errors where e.g. we could use an array function on a non-array variable
    fields: Array.isArray(dataset.fields) ? dataset.fields : [],
    manualFields: Array.isArray(dataset.manualFields) ? dataset.manualFields : [],
    mode,
    sourceFile: undefined,
  }
}


// Empty form, restore if set in GET param as resume=1
function initialForm() {
  const params = new URLSearchParams(globalThis.location.search)
  if (params.get('resume') !== '1') {
    return emptyForm
  }

  try {
    const saved = globalThis.localStorage.getItem(metadataDraftStorageKey)
    if (!saved) {
      return emptyForm
    }
    const parsed = JSON.parse(saved) as Partial<MetadataGeneratorForm>
    return {
      ...emptyForm,
      ...parsed,
      creators: Array.isArray(parsed.creators) ? parsed.creators : [],
      datasets: Array.isArray(parsed.datasets)
        ? parsed.datasets.map(restoreStoredDataset)
        : [],
    }
  } catch (storageError) {
    console.warn('Could not load metadata draft from localStorage.', storageError)
    return emptyForm
  }
}

/* The page breaks down this way:
1 - The main form elements
2 - Belonging to the main form really, the creators of the Adapter "creatorDraft".
3 - per dataset drafts
4 - Belonging to each datset draft, the dataset creator drafts

Important notes:
datasetManualField, formerly fieldDraft: Only for when the user drafts/wants to add a custom field to a dataset! Not the fields for the adapter itself.
selectedDatasetId: Solely for editing the details of datasets(and their creators)

 */
function CreateAdapterMetadataPage() {
  const [form, setForm] = useState<MetadataGeneratorForm>(initialForm)
  const [creatorDraft, setCreatorDraft] = useState<CreatorDraft>(emptyCreator)
  const [datasetDraft, setDatasetDraft] = useState<DatasetDraft>(emptyDataset)
  const [datasetCreatorDraft, setDatasetCreatorDraft] = useState<CreatorDraft>(emptyCreator)
  const [datasetManualField, setDatasetManualField] = useState<DatasetDatasetManualField>(emptyDatasetManualField)
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null)
  const [step, setStep] = useState<MetadataStep>(1)
  const [error, setError] = useState<string | null>(null)
  const [generatedMetadata, setGeneratedMetadata] = useState<Record<string, unknown> | null>(null)
  const [isGenerating, setIsGenerating] = useState(false) // flow controlling to avoid issues
  const [isPreparingDatasets, setIsPreparingDatasets] = useState(false)

  useEffect(() => {
    try {
      globalThis.localStorage.setItem(
        metadataDraftStorageKey,
        JSON.stringify(form, (_key, value) => {
          if (typeof File !== 'undefined' && value instanceof File) {
            return undefined
          }
          return value
        }),
      )
    } catch (storageError) {
      console.warn('Could not save metadata draft to localStorage.', storageError)
    }
  }, [form])

  useEffect(() => {
    globalThis.scrollTo({ left: 0, top: 0 })
  }, [step, generatedMetadata])

  function addCreator() {
    if (!creatorDraft.name.trim()) {
      setError('Add a creator name first.')
      return
    }

    setForm((current) => ({
      ...current,
      creators: [...current.creators, { ...creatorDraft, id: nextDraftId('creator') }],
    }))
    setCreatorDraft(emptyCreator)
    setError(null)
  }

  function removeCreator(id: string) {
    setForm((current) => ({
      ...current,
      creators: current.creators.filter((creator) => creator.id !== id),
    }))
  }

  function addDatasetCreator() {
    if (!datasetCreatorDraft.name.trim()) {
      setError('Add a dataset creator name first.')
      return
    }

    setDatasetDraft((current) => ({
      ...current,
      creators: [
        ...current.creators,
        { ...datasetCreatorDraft, id: nextDraftId('dataset-creator') },
      ],
    }))
    setDatasetCreatorDraft(emptyCreator)
    setError(null)
  }

  function removeDatasetCreator(id: string) {
    setDatasetDraft((current) => ({
      ...current,
      creators: current.creators.filter((creator) => creator.id !== id),
    }))
  }

  async function handleDatasetUpload(file: File | null) {
    if (!file) {
      return
    }

    try {
      const parsed = JSON.parse(await file.text()) as unknown
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        setError('Upload a JSON object Croissant file.')
        return
      }
      setDatasetDraft((current) => (
        datasetUIStateDraftFromCroissantFile(
          parsed as Record<string, unknown>,
          { ...current, mode: 'upload' },
          file.name,
        )
      ))
      setError(null)
    } catch (uploadError) {
      setError(errorText(uploadError, 'Could not read the Croissant file.'))
    }
  }

  function handleDatasetSourceUpload(file: File | null) {
    if (!file) {
      return
    }

    setDatasetDraft((current) => ({
      ...current,
      input: file.name,
      sourceFile: file,
      sourceFileName: file.name,
    }))
    setError(null)
  }

  function setDatasetMode(mode: DatasetMode) {
    setDatasetDraft({ ...emptyDataset, mode })
    setDatasetCreatorDraft(emptyCreator)
    setError(null)
  }

  function removeDataset(id: string) {
    setForm((current) => ({
      ...current,
      datasets: current.datasets.filter((dataset) => dataset.id !== id),
    }))
    setSelectedDatasetId((current) => {
      if (current !== id) {
        return current
      }
      return form.datasets.find((dataset) => dataset.id !== id)?.id ?? null
    })
  }

  function editDataset(id: string) {
    const datasetToEdit = form.datasets.find((dataset) => dataset.id === id)
    if (!datasetToEdit) {
      return
    }

    setDatasetDraft(datasetToEdit)
    setDatasetCreatorDraft(emptyCreator)
    setForm((current) => ({
      ...current,
      datasets: current.datasets.filter((dataset) => dataset.id !== id),
    }))
    setSelectedDatasetId((current) => (current === id ? null : current))
    setError(null)
  }

  function continueToDatasets() {
    const keywords = keywordsToApiValues(form.keywords)
    let creators = form.creators
    if (!creators.length && creatorDraft.name.trim()) {
      creators = [{ ...creatorDraft, id: nextDraftId('creator') }]
    }

    if (!form.name.trim() || !form.description.trim() || !form.version.trim()) {
      setError('Complete the required adapter details first.')
      return
    }

    if (!form.license.trim()) {
      setError('Choose an adapter license.')
      return
    }

    if (!form.codeRepository.trim()) {
      setError('Add a repository URL.')
      return
    }

    if (!creators.length) {
      setError('Add at least one adapter creator.')
      return
    }

    if (!keywords.length) {
      setError('Add at least one keyword.')
      return
    }

    if (!form.creators.length) {
      setForm((current) => ({ ...current, creators }))
      setCreatorDraft(emptyCreator)
    }

    setError(null)
    setStep(2)
  }

  async function prepareDatasetsForDetails() {
    const datasetsToPrepare = [...form.datasets]
    const hasPendingSourceFile = datasetDraft.mode === 'generate' && datasetDraft.sourceFile
    const hasPendingCroissantFile = datasetDraft.mode === 'upload' && datasetDraft.uploadedDocument
    if (hasPendingSourceFile || hasPendingCroissantFile) {
      datasetsToPrepare.push({ ...datasetDraft, id: nextDraftId('dataset') })
    }

    if (!datasetsToPrepare.length) {
      setError('Add at least one dataset.')
      return
    }

    setError(null)
    setIsPreparingDatasets(true)
    try {
      const datasets: DatasetDraft[] = []
      for (const dataset of datasetsToPrepare) {
        if (dataset.uploadedDocument) {
          datasets.push(dataset)
          continue
        }

        if (!dataset.sourceFile) {
          throw new Error('Upload a source dataset file first.')
        }

        const result = await generateDatasetMetadataApiV1MetadataDatasetsGeneratePost({
          body: datasetDraftToCroissantGenerateUploadForm(dataset),
        })
        if (result.error !== undefined) {
          throw new Error(errorText(result.error, 'Dataset generation failed.'))
        }
        if (!result.data) {
          throw new Error('Dataset generation did not return metadata.')
        }
        datasets.push(datasetUIStateDraftFromCroissantFile(result.data.metadata, dataset))
      }

      setForm((current) => ({ ...current, datasets }))
      setDatasetDraft(emptyDataset)
      setDatasetCreatorDraft(emptyCreator)
      setSelectedDatasetId((current) => current ?? datasets[0]?.id ?? null)
      setStep(3)
    } catch (prepareError) {
      setError(errorText(prepareError, 'Dataset generation failed.'))
    } finally {
      setIsPreparingDatasets(false)
    }
  }


  function updateSelectedDatasetDraft(
    updateDataset: (dataset: DatasetDraft) => DatasetDraft,
  ) {
    if (!selectedDatasetId) {
      return
    }

    setForm((current) => ({
      ...current,
      datasets: current.datasets.map((dataset) => {
        if (dataset.id !== selectedDatasetId) {
          return dataset
        }
        return updateDataset(dataset)
      }),
    }))
  }

  function updateSelectedDataset(field: keyof DatasetDraft, value: string) {
    updateSelectedDatasetDraft((dataset) => ({ ...dataset, [field]: value }))
  }

  function updateSelectedField(
    fieldId: string,
    fieldName: keyof DatasetDatasetManualField,
    value: string,
  ) {
    updateSelectedDatasetDraft((dataset) => ({
      ...dataset,
      fields: updateFieldList(dataset.fields, fieldId, fieldName, value),
      manualFields: updateFieldList(dataset.manualFields, fieldId, fieldName, value),
    }))
  }

  function addManualField() {
    if (!selectedDatasetId) {
      return
    }

    if (!datasetManualField.name.trim() || !datasetManualField.dataType.trim()) {
      setError('Add a field name and datatype first.')
      return
    }

    updateSelectedDatasetDraft((dataset) => ({
      ...dataset,
      manualFields: [
        ...dataset.manualFields,
        { ...datasetManualField, id: nextDraftId('manual-field') },
      ],
    }))
    setDatasetManualField(emptyDatasetManualField())
    setError(null)
  }

  function removeSelectedField(fieldId: string) {
    updateSelectedDatasetDraft((dataset) => ({
      ...dataset,
      fields: dataset.fields.filter((field) => field.id !== fieldId),
      manualFields: dataset.manualFields.filter((field) => field.id !== fieldId),
    }))
  }

  async function generateMetadata() {
    const creators = form.creators.map(creatorToApiValue)
    const keywords = keywordsToApiValues(form.keywords)
    const datasetDocuments = form.datasets.map(datasetDraftToDocument)

    if (!form.license.trim()) {
      setError('Choose an adapter license.')
      return
    }

    if (!datasetDocuments.length) {
      setError('Add at least one dataset.')
      return
    }

    setError(null)
    setStep(4)
    setIsGenerating(true)
    try {
      const result = await generateAdapterMetadataApiV1MetadataAdaptersGeneratePost({
        body: {
          adapter_id: optionalValue(form.adapterId),
          code_repository: form.codeRepository,
          creators,
          dataset_documents: datasetDocuments,
          dataset_paths: [],
          generated_datasets: [],
          generator: 'native',
          keywords,
          license: form.license,
          name: form.name,
          version: form.version,
          description: form.description,
        },
      })

      if (result.error !== undefined) {
        setError(errorText(result.error, 'Metadata generation failed.'))
        return
      }

      if (!result.data) {
        setError('Metadata generation did not return a Croissant document.')
        return
      }

      setGeneratedMetadata(result.data.metadata)
      setError(null)
    } catch (metadataError) {
      setError(errorText(metadataError, 'Metadata generation failed.'))
    } finally {
      setIsGenerating(false)
    }
  }

  function handleMetadataSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (step === 1) {
      continueToDatasets()
      return
    }
    if (step === 2) {
      void prepareDatasetsForDetails()
      return
    }
    void generateMetadata()
  }

  const selectedDataset = form.datasets.find((dataset) => dataset.id === selectedDatasetId)
  const generatedMetadataJson = generatedMetadata
    ? JSON.stringify(generatedMetadata, undefined, 2)
    : ''

  return (
    <section className="bg-slate-100">
      <div className="mx-auto max-w-7xl px-6 py-14 md:py-18">
        <div className="mb-10">
          <h1 className="max-w-4xl text-4xl font-bold tracking-normal text-slate-950 md:text-5xl">
            Create a Metadata File for an Adapter
          </h1>
        </div>

        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start">
          {generatedMetadata ? (
            <MetadataReadyPanel
              adapterName={form.name}
              metadata={generatedMetadata}
              metadataJson={generatedMetadataJson}
              onBack={() => {
                setGeneratedMetadata(null)
                setStep(3)
              }}
            />
          ) : (
          <form className="grid gap-8" onSubmit={handleMetadataSubmit}>
            {step === 1 ? (
              <AdapterDetailsStep
                creatorDraft={creatorDraft}
                form={form}
                onAddCreator={addCreator}
                onCreatorDraftChange={(field, value) => {
                  setCreatorDraft((current) => ({ ...current, [field]: value }))
                }}
                onFormChange={(field, value) => {
                  setForm((current) => ({ ...current, [field]: value }))
                }}
                onRemoveCreator={removeCreator}
              />
            ) : null}

            {step === 2 ? (
              <DatasetBasicsStep
                datasetCreatorDraft={datasetCreatorDraft}
                datasetDraft={datasetDraft}
                datasets={form.datasets}
                onAddDatasetCreator={addDatasetCreator}
                onDatasetCreatorDraftChange={(field, value) => {
                  setDatasetCreatorDraft((current) => ({ ...current, [field]: value }))
                }}
                onDatasetDraftChange={(field, value) => {
                  setDatasetDraft((current) => ({ ...current, [field]: value }))
                }}
                onDatasetModeChange={setDatasetMode}
                onDatasetUpload={handleDatasetUpload}
                onDatasetSourceUpload={handleDatasetSourceUpload}
                onEditDataset={editDataset}
                onRemoveDataset={removeDataset}
                onRemoveDatasetCreator={removeDatasetCreator}
              />
            ) : null}

            {step >= 3 ? (
              <DatasetDetailsStep
                datasets={form.datasets}
                datasetManualField={datasetManualField}
                onAddManualField={addManualField}
                onDatasetChange={updateSelectedDataset}
                onFieldChange={updateSelectedField}
                onManualFieldChange={(field, value) => {
                  setDatasetManualField((current) => ({ ...current, [field]: value }))
                }}
                onRemoveDataset={removeDataset}
                onRemoveField={removeSelectedField}
                onSelectDataset={setSelectedDatasetId}
                selectedDataset={selectedDataset}
                selectedDatasetId={selectedDatasetId}
              />
            ) : null}

            <div className="flex flex-col gap-4 border-t border-slate-200 pt-8 md:flex-row md:items-center md:justify-between">
              <div className="flex gap-3">
                {step > 1 && step < 4 ? (
                  <button
                    className="h-12 rounded-lg border border-slate-200 bg-white px-5 text-base font-semibold text-slate-950 hover:border-blue-300"
                    onClick={() => setStep((current) => (current - 1) as MetadataStep)}
                    type="button"
                  >
                    Back
                  </button>
                ) : null}
              </div>

              <div className="flex flex-col gap-4 md:items-end">
                {error ? (
                  <p className="w-full rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 md:min-w-96">
                    {error}
                  </p>
                ) : null}
                {step === 1 ? (
                  <button
                    className="h-12 rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700"
                    type="submit"
                  >
                    Continue
                  </button>
                ) : null}
                {step === 2 ? (
                  <button
                    className="h-12 rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
                    disabled={isPreparingDatasets}
                    type="submit"
                  >
                    {isPreparingDatasets ? 'Adding dataset...' : 'Add dataset'}
                  </button>
                ) : null}
                {step >= 3 ? (
                  <button
                    className="inline-flex h-14 cursor-pointer items-center justify-center gap-3 rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
                    disabled={isGenerating}
                    type="submit"
                  >
                    {isGenerating ? 'Generating...' : 'Finish this stage'}
                    <ArrowDownTrayIcon className="h-5 w-5" aria-hidden="true" />
                  </button>
                ) : null}
              </div>
            </div>
          </form>
          )}

          <Stepper currentStep={step} />
        </div>
      </div>
    </section>
  )
}

// Final results panel, for croissant file export
function MetadataReadyPanel({
  adapterName,
  metadata,
  metadataJson,
  onBack,
}: Readonly<{
  adapterName: string
  metadata: Record<string, unknown>
  metadataJson: string
  onBack: () => void
}>) {
  const datasetCount = Array.isArray(metadata.hasPart) ? metadata.hasPart.length : 0

  return (
    <section className="grid gap-6">
      <div>
        <h2 className="text-3xl font-bold text-slate-950">Adapter ready</h2>
        <p className="mt-3 max-w-3xl text-base leading-7 text-slate-600">
          Your adapter metadata was generated successfully. Review the JSON-LD preview and download the final Croissant file.
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <dl className="grid gap-4 text-sm md:grid-cols-3">
          <div>
            <dt className="font-semibold text-slate-500">Adapter</dt>
            <dd className="mt-1 font-bold text-slate-950">{adapterName || 'Untitled adapter'}</dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-500">Datasets</dt>
            <dd className="mt-1 font-bold text-slate-950">{datasetCount}</dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-500">Format</dt>
            <dd className="mt-1 font-bold text-slate-950">JSON-LD</dd>
          </div>
        </dl>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="text-xl font-bold text-slate-950">JSON-LD preview</h3>
        <pre className="mt-4 max-h-96 overflow-auto rounded-xl bg-slate-100 p-5 text-xs leading-5 text-slate-950">
          {metadataJson}
        </pre>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:justify-end">
          <button
            className="h-10 rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-950 hover:border-blue-300"
            onClick={onBack}
            type="button"
          >
            Back to form
          </button>
          <button
            className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700"
            onClick={() => downloadMetadata(metadata, adapterName)}
            type="button"
          >
            <ArrowDownTrayIcon className="h-5 w-5" aria-hidden="true" />
            Download finished Croissant file
          </button>
        </div>
      </div>
    </section>
  )
}


function updateFieldList(
  fields: DatasetDatasetManualField[],
  fieldId: string,
  fieldName: keyof DatasetDatasetManualField,
  value: string,
) {
  return fields.map((field) => {
    if (field.id !== fieldId) {
      return field
    }
    return { ...field, [fieldName]: value }
  })
}

export default CreateAdapterMetadataPage
