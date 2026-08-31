import { useEffect, useRef, useState, type FormEvent } from 'react'
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

function hasRestorableDatasetDocument(dataset: unknown): dataset is Partial<DatasetDraft> {
  if (typeof dataset !== 'object' || dataset === null || Array.isArray(dataset)) {
    return false
  }

  const document = (dataset as Partial<DatasetDraft>).uploadedDocument
  return typeof document === 'object' && document !== null && !Array.isArray(document)
}

function restorableDatasets(datasets: unknown): DatasetDraft[] {
  if (!Array.isArray(datasets)) {
    return []
  }

  return datasets
    .filter(hasRestorableDatasetDocument)
    .map(restoreStoredDataset)
}

function formForStorage(form: MetadataGeneratorForm): MetadataGeneratorForm {
  return {
    ...form,
    datasets: restorableDatasets(form.datasets),
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
      datasets: restorableDatasets(parsed.datasets),
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
  const formRef = useRef<HTMLFormElement>(null)
  const [form, setForm] = useState<MetadataGeneratorForm>(initialForm)
  const [creatorDraft, setCreatorDraft] = useState<CreatorDraft>(emptyCreator)
  const [datasetDraft, setDatasetDraft] = useState<DatasetDraft>(emptyDataset)
  const [datasetCreatorDraft, setDatasetCreatorDraft] = useState<CreatorDraft>(emptyCreator)
  const [datasetManualField, setDatasetManualField] = useState<DatasetDatasetManualField>(emptyDatasetManualField)
  const [editingCreatorId, setEditingCreatorId] = useState<string | null>(null)
  const [editingDatasetCreatorId, setEditingDatasetCreatorId] = useState<string | null>(null)
  const [editingDatasetId, setEditingDatasetId] = useState<string | null>(null)
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
        JSON.stringify(formForStorage(form)),
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
      creators: editingCreatorId
        ? current.creators.map((creator) => {
          if (creator.id !== editingCreatorId) {
            return creator
          }
          return { ...creatorDraft, id: editingCreatorId }
        })
        : [...current.creators, { ...creatorDraft, id: nextDraftId('creator') }],
    }))
    setCreatorDraft(emptyCreator)
    setEditingCreatorId(null)
    setError(null)
  }

  function editCreator(id: string) {
    const creatorToEdit = form.creators.find((creator) => creator.id === id)
    if (!creatorToEdit) {
      return
    }

    setCreatorDraft(creatorToEdit)
    setEditingCreatorId(id)
    setError(null)
  }

  function removeCreator(id: string) {
    if (editingCreatorId === id) {
      setCreatorDraft(emptyCreator)
      setEditingCreatorId(null)
    }

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
      creators: editingDatasetCreatorId
        ? current.creators.map((creator) => {
          if (creator.id !== editingDatasetCreatorId) {
            return creator
          }
          return { ...datasetCreatorDraft, id: editingDatasetCreatorId }
        })
        : [
          ...current.creators,
          { ...datasetCreatorDraft, id: nextDraftId('dataset-creator') },
        ],
    }))
    setDatasetCreatorDraft(emptyCreator)
    setEditingDatasetCreatorId(null)
    setError(null)
  }

  function editDatasetCreator(id: string) {
    const creatorToEdit = datasetDraft.creators.find((creator) => creator.id === id)
    if (!creatorToEdit) {
      return
    }

    setDatasetCreatorDraft(creatorToEdit)
    setEditingDatasetCreatorId(id)
    setError(null)
  }

  function removeDatasetCreator(id: string) {
    if (editingDatasetCreatorId === id) {
      setDatasetCreatorDraft(emptyCreator)
      setEditingDatasetCreatorId(null)
    }

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
      uploadedDocument: undefined,
    }))
    setError(null)
  }

  function setDatasetMode(mode: DatasetMode) {
    setDatasetDraft((current) => ({ ...emptyDataset, id: current.id, mode }))
    setDatasetCreatorDraft(emptyCreator)
    setEditingDatasetCreatorId(null)
    setError(null)
  }

  function removeDataset(id: string) {
    if (editingDatasetId === id) {
      setDatasetDraft(emptyDataset)
      setDatasetCreatorDraft(emptyCreator)
      setEditingDatasetCreatorId(null)
      setEditingDatasetId(null)
    }

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
    setEditingDatasetCreatorId(null)
    setEditingDatasetId(id)
    setSelectedDatasetId(id)
    setError(null)
    globalThis.requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({ block: 'start' })
    })
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

  async function prepareDatasetsForDetails(nextStep: MetadataStep = 3, shouldGenerateMetadata = false) {
    let datasetsToPrepare = [...form.datasets]
    let nextSelectedDatasetId: string | null = null
    const hasPendingSourceFile = datasetDraft.mode === 'generate' && datasetDraft.sourceFile && !datasetDraft.uploadedDocument
    const hasPendingCroissantFile = datasetDraft.mode === 'upload' && datasetDraft.uploadedDocument
    if (editingDatasetId) {
      nextSelectedDatasetId = editingDatasetId
      datasetsToPrepare = datasetsToPrepare.map((dataset) => {
        if (dataset.id !== editingDatasetId) {
          return dataset
        }
        return datasetDraft
      })
    } else if (hasPendingSourceFile || hasPendingCroissantFile) {
      const datasetToAdd = { ...datasetDraft, id: nextDraftId('dataset') }
      nextSelectedDatasetId = datasetToAdd.id
      datasetsToPrepare.push(datasetToAdd)
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
      setEditingDatasetCreatorId(null)
      setEditingDatasetId(null)
      if (shouldGenerateMetadata) {
        await generateMetadata(datasets)
        return
      }
      setSelectedDatasetId((current) => nextSelectedDatasetId ?? current ?? datasets[0]?.id ?? null)
      setStep(nextStep)
    } catch (prepareError) {
      setError(errorText(prepareError, 'Dataset generation failed.'))
    } finally {
      setIsPreparingDatasets(false)
    }
  }


  function updateSelectedDatasetDraft(
    updateDataset: (dataset: DatasetDraft) => DatasetDraft,
  ) {
    if (editingDatasetId) {
      setDatasetDraft(updateDataset)
      return
    }

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
    if (!editingDatasetId && !selectedDatasetId) {
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

  async function generateMetadata(datasets: DatasetDraft[] = form.datasets) {
    const creators = form.creators.map(creatorToApiValue)
    const keywords = keywordsToApiValues(form.keywords)

    if (!form.license.trim()) {
      setError('Choose an adapter license.')
      return
    }

    if (!datasets.length) {
      setError('Add at least one dataset.')
      return
    }

    if (datasets.some((dataset) => !dataset.datasetVersion.trim() || !dataset.datePublished.trim())) {
      setError('Add a dataset version and date published before generating Croissant metadata.')
      return
    }

    const datasetDocuments = datasets.map(datasetDraftToDocument)

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
    if (editingDatasetId) {
      void prepareDatasetsForDetails(2)
      return
    }
    if (step === 2) {
      void prepareDatasetsForDetails()
      return
    }
    void generateMetadata()
  }

  const isEditingDataset = Boolean(editingDatasetId)
  const selectedDataset = isEditingDataset
    ? datasetDraft
    : form.datasets.find((dataset) => dataset.id === selectedDatasetId)
  const generatedMetadataJson = generatedMetadata
    ? JSON.stringify(generatedMetadata, undefined, 2)
    : ''
  let datasetSubmitLabel = 'Add dataset'
  if (isPreparingDatasets) {
    datasetSubmitLabel = editingDatasetId ? 'Saving changes...' : 'Saving dataset...'
  } else if (editingDatasetId) {
    datasetSubmitLabel = 'Save changes'
  }

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
          <form className="grid gap-8" onSubmit={handleMetadataSubmit} ref={formRef}>
            {step === 1 ? (
              <AdapterDetailsStep
                creatorActionLabel={editingCreatorId ? 'Save creator' : 'Add creator'}
                creatorDraft={creatorDraft}
                form={form}
                onAddCreator={addCreator}
                onCreatorDraftChange={(field, value) => {
                  setCreatorDraft((current) => ({ ...current, [field]: value }))
                }}
                onEditCreator={editCreator}
                onFormChange={(field, value) => {
                  setForm((current) => {
                    if (field !== 'name') {
                      return { ...current, [field]: value }
                    }

                    const shouldUpdateAdapterId = !current.adapterId.trim()
                      || current.adapterId === adapterIdFromName(current.name)
                    if (!shouldUpdateAdapterId) {
                      return { ...current, name: value }
                    }

                    return { ...current, name: value, adapterId: adapterIdFromName(value) }
                  })
                }}
                onRemoveCreator={removeCreator}
              />
            ) : null}

            {step === 2 || isEditingDataset ? (
              <DatasetBasicsStep
                datasetCreatorActionLabel={editingDatasetCreatorId ? 'Save creator' : 'Add creator'}
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
                onEditDatasetCreator={editDatasetCreator}
                onEditDataset={editDataset}
                onRemoveDataset={removeDataset}
                onRemoveDatasetCreator={removeDatasetCreator}
              />
            ) : null}

            {step >= 3 || isEditingDataset ? (
              <DatasetDetailsStep
                datasets={form.datasets}
                datasetManualField={datasetManualField}
                hideOverview={isEditingDataset}
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
                {isEditingDataset ? (
                  <button
                    className="inline-flex h-12 cursor-pointer items-center justify-center gap-3 rounded-lg border border-slate-200 bg-white px-5 text-base font-semibold text-slate-950 hover:border-blue-300 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500"
                    disabled={isGenerating || isPreparingDatasets}
                    onClick={(event) => {
                      const formElement = event.currentTarget.form
                      if (formElement && !formElement.reportValidity()) {
                        return
                      }
                      void prepareDatasetsForDetails(4, true)
                    }}
                    type="button"
                  >
                    Finalize datasets - Generate Croissant Now
                    <ArrowDownTrayIcon className="h-5 w-5" aria-hidden="true" />
                  </button>
                ) : null}
                {!isEditingDataset && step === 2 ? (
                  <button
                    className="h-12 rounded-lg border border-slate-200 bg-white px-5 text-base font-semibold text-slate-950 hover:border-blue-300"
                    onClick={() => setStep((current) => (current - 1) as MetadataStep)}
                    type="button"
                  >
                    Back
                  </button>
                ) : null}
                {!isEditingDataset && step === 3 ? (
                  <button
                    className="h-12 rounded-lg border border-slate-200 bg-white px-5 text-base font-semibold text-slate-950 hover:border-blue-300"
                    onClick={(event) => {
                      const formElement = event.currentTarget.form
                      if (formElement && !formElement.reportValidity()) {
                        return
                      }
                      setDatasetDraft(emptyDataset)
                      setDatasetCreatorDraft(emptyCreator)
                      setEditingDatasetCreatorId(null)
                      setEditingDatasetId(null)
                      setSelectedDatasetId(null)
                      setError(null)
                      setStep(2)
                    }}
                    type="button"
                  >
                    Add another dataset & Save
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
                    {datasetSubmitLabel}
                  </button>
                ) : null}
                {step >= 3 && !isEditingDataset ? (
                  <button
                    className="inline-flex h-14 cursor-pointer items-center justify-center gap-3 rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
                    disabled={isGenerating}
                    type="submit"
                  >
                    {isGenerating ? 'Generating...' : 'Finalize datasets - Generate Croissant Now'}
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
            onClick={() => downloadMetadata(metadata)}
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

function adapterIdFromName(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export default CreateAdapterMetadataPage
