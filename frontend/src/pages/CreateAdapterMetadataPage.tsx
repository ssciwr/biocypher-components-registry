import { useEffect, useRef, useState, type ReactNode, type SubmitEvent } from 'react'
import { ArrowDownTrayIcon, CheckCircleIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import {
  generateAdapterMetadataApiV1MetadataAdaptersGeneratePost,
  type MetadataValidationResponse,
} from '../api/client'
import { registrationValidationDetails } from '../api/validationDiagnostics'
import { DiagnosticErrors, RegistrationValidationChecks } from '../components/RegistrationValidationChecks'
import {
  AdapterDetailsStep,
  DatasetBasicsStep,
  DatasetDetailsStep,
} from './createMetadata/MetadataGeneratorSteps'
import { datasetMetadataSectionId } from './createMetadata/MetadataGeneratorFields'
import { emptyCreator, emptyDataset, emptyForm } from './createMetadata/options'
import type {
  CreatorDraft,
  DatasetDraft,
  DatasetDatasetManualField,
  DatasetMode,
  DatasetSourceSelection,
  MetadataGeneratorForm,
  MetadataStep,
} from './createMetadata/types'
import {
  DatasetCapacityCancelledError,
  type DatasetCapacityWait,
} from './createMetadata/datasetUpload'
import { prepareDatasetDrafts } from './createMetadata/datasetPreparation'
import {
  creatorToApiValue,
  datasetUIStateDraftFromCroissantFile,
  datasetDraftToDocument,
  downloadMetadata,
  emptyDatasetManualField,
  errorText,
  keywordsToApiValues,
  nextDraftId,
  optionalValue,
} from './createMetadata/utils'
import { hasMeaningfulMetadataDraft, metadataDraftStorageKey } from './createMetadata/storage'

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
    distributions: Array.isArray(dataset.distributions) ? dataset.distributions : [],
    fields: Array.isArray(dataset.fields) ? dataset.fields : [],
    manualFields: Array.isArray(dataset.manualFields) ? dataset.manualFields : [],
    recordSets: Array.isArray(dataset.recordSets) ? dataset.recordSets : [],
    mode,
    sourceSelection: undefined,
    uploadedDirtyFields: Array.isArray(dataset.uploadedDirtyFields)
      ? dataset.uploadedDirtyFields
      : [],
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

// Right after clicking "Add Creator"
function focusCreatorNameInput(inputName: string) {
  globalThis.requestAnimationFrame(() => {
    const creatorNameInput = globalThis.document.querySelector<HTMLInputElement>(`input[name="${inputName}"]`)
    creatorNameInput?.focus({ preventScroll: true })
    globalThis.scrollTo({ left: 0, top: globalThis.document.documentElement.scrollHeight, behavior: 'smooth' })
  })
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
  if (params.get('start') === '1') {
    globalThis.localStorage.removeItem(metadataDraftStorageKey)
    return emptyForm
  }
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

function MetadataStepContent({
  adapterStep,
  datasetBasicsStep,
  datasetDetailsStep,
  isEditingDataset,
  step,
}: Readonly<{
  adapterStep: ReactNode
  datasetBasicsStep: ReactNode
  datasetDetailsStep: ReactNode
  isEditingDataset: boolean
  step: MetadataStep
}>) {
  if (step === 1) return adapterStep
  if (step === 2 && !isEditingDataset) return datasetBasicsStep
  if (step >= 3 || isEditingDataset) return datasetDetailsStep
  return null
}

function MetadataFormFooter({
  addDatasetAction,
  backAction,
  capacityWait,
  continueAction,
  datasetAction,
  editingDatasetAction,
  error,
  generateAction,
  isEditingDataset,
  isReviewingDatasets,
  selectedDataset,
  selectedDatasetAction,
  step,
  warning,
}: Readonly<{
  addDatasetAction: ReactNode
  backAction: ReactNode
  capacityWait: DatasetCapacityWait | null
  continueAction: ReactNode
  datasetAction: ReactNode
  editingDatasetAction: ReactNode
  error: string | null
  generateAction: ReactNode
  isEditingDataset: boolean
  isReviewingDatasets: boolean
  selectedDataset: DatasetDraft | undefined
  selectedDatasetAction: ReactNode
  step: MetadataStep
  warning: string | null
}>) {
  return (
    <div className="flex flex-col gap-4 border-t border-slate-200 pt-8 md:flex-row md:items-center md:justify-between">
      <div className="flex gap-3">
        {!isEditingDataset && step === 2 ? backAction : null}
      </div>
      <div className="flex flex-col gap-4 md:items-end">
        {capacityWait ? <CapacityWaitPanel wait={capacityWait} /> : null}
        {error ? (
          <p className="w-full rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 md:min-w-96">{error}</p>
        ) : null}
        {warning ? (
          <p className="w-full rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 md:min-w-96">{warning}</p>
        ) : null}
        {step === 1 ? continueAction : null}
        {step === 2 && !isEditingDataset ? datasetAction : null}
        {isEditingDataset ? editingDatasetAction : null}
        {step >= 3 && !isEditingDataset && selectedDataset ? selectedDatasetAction : null}
        {isReviewingDatasets ? (
          <div className="flex flex-wrap justify-end gap-3">
            {addDatasetAction}
            {generateAction}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function metadataPageViewState({
  datasetDraft,
  editingDatasetId,
  form,
  generatedMetadata,
  isPreparingDatasets,
  selectedDatasetId,
  step,
}: Readonly<{
  datasetDraft: DatasetDraft
  editingDatasetId: string | null
  form: MetadataGeneratorForm
  generatedMetadata: Record<string, unknown> | null
  isPreparingDatasets: boolean
  selectedDatasetId: string | null
  step: MetadataStep
}>) {
  const isEditingDataset = Boolean(editingDatasetId)
  const selectedDataset = isEditingDataset
    ? datasetDraft
    : form.datasets.find((dataset) => dataset.id === selectedDatasetId)
  const isReviewingDatasets = step >= 3 && !isEditingDataset && !selectedDataset
  const generatedMetadataJson = generatedMetadata
    ? JSON.stringify(generatedMetadata, undefined, 2)
    : ''
  let datasetSubmitLabel = datasetDraft.mode === 'generate' ? 'Add dataset details' : 'Add dataset'
  if (isPreparingDatasets) {
    datasetSubmitLabel = editingDatasetId ? 'Saving changes...' : 'Saving dataset...'
  } else if (editingDatasetId) {
    datasetSubmitLabel = 'Save changes'
  }
  return {
    datasetSubmitLabel,
    generatedMetadataJson,
    isEditingDataset,
    isReviewingDatasets,
    selectedDataset,
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
  const [warning, setWarning] = useState<string | null>(null)
  const [generatedMetadata, setGeneratedMetadata] = useState<Record<string, unknown> | null>(null)
  const [generationValidation, setGenerationValidation] = useState<MetadataValidationResponse | null>(null)
  const [isGenerating, setIsGenerating] = useState(false) // flow controlling to avoid issues
  const [isPreparingDatasets, setIsPreparingDatasets] = useState(false)
  const [capacityWait, setCapacityWait] = useState<DatasetCapacityWait | null>(null)

  useEffect(() => {
    try {
      const restorableForm = formForStorage(form)
      if (hasMeaningfulMetadataDraft(restorableForm)) {
        globalThis.localStorage.setItem(
          metadataDraftStorageKey,
          JSON.stringify(restorableForm),
        )
      } else {
        globalThis.localStorage.removeItem(metadataDraftStorageKey)
      }
    } catch (storageError) {
      console.warn('Could not save metadata draft to localStorage.', storageError)
    }
  }, [form])

  useEffect(() => {
    if (step >= 3 && selectedDatasetId && !generatedMetadata) {
      globalThis.requestAnimationFrame(() => {
        // Scroll to what the user should pay attention to (i.e. the dataset form inputs)
        globalThis.document.getElementById(datasetMetadataSectionId)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
      })
      return
    }

    globalThis.scrollTo({ left: 0, top: 0 })
  }, [generatedMetadata, selectedDatasetId, step])

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
    focusCreatorNameInput('adapter-creator-name')
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

    updateActiveDatasetDraft((current) => ({
      ...current,
      uploadedDirtyFields: current.mode === 'upload'
        ? [...new Set([...current.uploadedDirtyFields, 'creators' as const])]
        : current.uploadedDirtyFields,
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
    const activeDataset = editingDatasetId || step === 2
      ? datasetDraft
      : form.datasets.find((dataset) => dataset.id === selectedDatasetId)
    const creatorToEdit = activeDataset?.creators.find((creator) => creator.id === id)
    if (!creatorToEdit) {
      return
    }

    setDatasetCreatorDraft(creatorToEdit)
    setEditingDatasetCreatorId(id)
    setError(null)
    focusCreatorNameInput(editingDatasetId || step !== 2
      ? 'dataset-details-creator-name'
      : 'dataset-creator-name')
  }

  function removeDatasetCreator(id: string) {
    if (editingDatasetCreatorId === id) {
      setDatasetCreatorDraft(emptyCreator)
      setEditingDatasetCreatorId(null)
    }

    updateActiveDatasetDraft((current) => ({
      ...current,
      creators: current.creators.filter((creator) => creator.id !== id),
      uploadedDirtyFields: current.mode === 'upload'
        ? [...new Set([...current.uploadedDirtyFields, 'creators' as const])]
        : current.uploadedDirtyFields,
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

  function handleDatasetSourceUpload(selection: DatasetSourceSelection | null) {
    if (!selection) {
      return
    }

    setDatasetDraft((current) => ({
      ...current,
      input: selection.name,
      sourceSelection: selection,
      sourceFileName: selection.kind === 'folder'
        ? `${selection.name} (${selection.entries.length} files)`
        : selection.name,
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

  async function prepareDatasetsForDetails(
    nextStep: MetadataStep = 3,
    shouldGenerateMetadata = false,
    shouldReviewDatasets = false,
  ) {
    let datasetsToPrepare = [...form.datasets]
    let nextSelectedDatasetId: string | null = null
    const hasPendingSourceFile = datasetDraft.mode === 'generate' && datasetDraft.sourceSelection && !datasetDraft.uploadedDocument
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
    setWarning(null)
    setIsPreparingDatasets(true)
    try {
      const { datasets, warnings: generationWarnings } = await prepareDatasetDrafts(
        datasetsToPrepare,
        setCapacityWait,
      )

      setForm((current) => ({ ...current, datasets }))
      setDatasetDraft(emptyDataset)
      setDatasetCreatorDraft(emptyCreator)
      setEditingDatasetCreatorId(null)
      setEditingDatasetId(null)
      setWarning(generationWarnings.length ? generationWarnings.join(' ') : null)
      if (shouldGenerateMetadata) {
        await generateMetadata(datasets)
        return
      }
      setSelectedDatasetId((current) => (
        shouldReviewDatasets ? null : nextSelectedDatasetId ?? current ?? datasets[0]?.id ?? null
      ))
      setStep(nextStep)
    } catch (prepareError) {
      if (prepareError instanceof DatasetCapacityCancelledError) {
        return
      }
      setError(errorText(prepareError, 'Dataset generation failed.'))
    } finally {
      setCapacityWait(null)
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

  function updateActiveDatasetDraft(
    updateDataset: (dataset: DatasetDraft) => DatasetDraft,
  ) {
    if (editingDatasetId || step === 2) {
      setDatasetDraft(updateDataset)
      return
    }
    updateSelectedDatasetDraft(updateDataset)
  }

  function updateSelectedDataset(field: keyof DatasetDraft, value: string) {
    const uploadedDirtyField = field === 'recordSetName' ? 'fields' : field
    updateSelectedDatasetDraft((dataset) => ({
      ...dataset,
      [field]: value,
      uploadedDirtyFields: dataset.mode === 'upload'
        ? [...new Set([...dataset.uploadedDirtyFields, uploadedDirtyField as typeof dataset.uploadedDirtyFields[number]])]
        : dataset.uploadedDirtyFields,
    }))
  }

  function updateSelectedField(
    recordSetIndex: number | undefined,
    fieldId: string,
    fieldName: keyof DatasetDatasetManualField,
    value: string,
  ) {
    updateSelectedDatasetDraft((dataset) => ({
      ...dataset,
      fields: recordSetIndex === undefined
        ? updateFieldList(dataset.fields, fieldId, fieldName, value)
        : dataset.fields,
      manualFields: updateFieldList(dataset.manualFields, fieldId, fieldName, value),
      recordSets: recordSetIndex === undefined
        ? dataset.recordSets
        : dataset.recordSets.map((recordSet, index) => index === recordSetIndex
          ? { ...recordSet, fields: updateFieldList(recordSet.fields, fieldId, fieldName, value) }
          : recordSet),
      uploadedDirtyFields: dataset.mode === 'upload'
        ? [...new Set([...dataset.uploadedDirtyFields, 'fields' as const])]
        : dataset.uploadedDirtyFields,
    }))
  }

  function updateSelectedDistribution(
    distributionIndex: number,
    field: 'contentUrl' | 'encodingFormat' | 'filename' | 'md5' | 'sha256',
    value: string,
  ) {
    updateSelectedDatasetDraft((dataset) => ({
      ...dataset,
      distributions: dataset.distributions.map((distribution, index) => (
        index === distributionIndex ? { ...distribution, [field]: value } : distribution
      )),
      uploadedDirtyFields: dataset.mode === 'upload'
        ? [...new Set([...dataset.uploadedDirtyFields, 'distributions' as const])]
        : dataset.uploadedDirtyFields,
    }))
  }

  function addManualField(recordSetIndex?: number) {
    if (!editingDatasetId && !selectedDatasetId) {
      return
    }

    if (!datasetManualField.name.trim() || !datasetManualField.dataType.trim()) {
      setError('Add a field name and datatype first.')
      return
    }

    updateSelectedDatasetDraft((dataset) => ({
      ...dataset,
      manualFields: recordSetIndex === undefined ? [
        ...dataset.manualFields,
        { ...datasetManualField, id: nextDraftId('manual-field') },
      ] : dataset.manualFields,
      recordSets: recordSetIndex === undefined
        ? dataset.recordSets
        : dataset.recordSets.map((recordSet, index) => index === recordSetIndex
          ? {
            ...recordSet,
            fields: [...recordSet.fields, { ...datasetManualField, id: nextDraftId('manual-field') }],
          }
          : recordSet),
      uploadedDirtyFields: dataset.mode === 'upload'
        ? [...new Set([...dataset.uploadedDirtyFields, 'fields' as const])]
        : dataset.uploadedDirtyFields,
    }))
    setDatasetManualField(emptyDatasetManualField())
    setError(null)
  }

  function validateDatasetDetails(formElement: HTMLFormElement | null) {
    if (formElement && !formElement.reportValidity()) {
      return false
    }
    setError(null)
    return true
  }

  function removeSelectedField(recordSetIndex: number | undefined, fieldId: string) {
    updateSelectedDatasetDraft((dataset) => ({
      ...dataset,
      fields: dataset.fields.filter((field) => field.id !== fieldId),
      manualFields: dataset.manualFields.filter((field) => field.id !== fieldId),
      recordSets: recordSetIndex === undefined
        ? dataset.recordSets
        : dataset.recordSets.map((recordSet, index) => index === recordSetIndex
          ? { ...recordSet, fields: recordSet.fields.filter((field) => field.id !== fieldId) }
          : recordSet),
      uploadedDirtyFields: dataset.mode === 'upload'
        ? [...new Set([...dataset.uploadedDirtyFields, 'fields' as const])]
        : dataset.uploadedDirtyFields,
    }))
  }

  function updateSelectedRecordSetName(recordSetIndex: number, value: string) {
    updateSelectedDatasetDraft((dataset) => ({
      ...dataset,
      recordSets: dataset.recordSets.map((recordSet, index) => (
        index === recordSetIndex ? { ...recordSet, name: value } : recordSet
      )),
      uploadedDirtyFields: dataset.mode === 'upload'
        ? [...new Set([...dataset.uploadedDirtyFields, 'fields' as const])]
        : dataset.uploadedDirtyFields,
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

    if (datasets.some((dataset) => (
      dataset.mode === 'generate'
      && (!dataset.datasetVersion.trim() || !dataset.datePublished.trim())
    ))) {
      setError('Add a dataset version and date published before generating Croissant metadata.')
      return
    }

    const datasetDocuments = datasets.map(datasetDraftToDocument)

    setError(null)
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

      setStep(4)
      setGeneratedMetadata(result.data.metadata)
      setGenerationValidation(result.data.validation ?? null)
      setError(null)
    } catch (metadataError) {
      setError(errorText(metadataError, 'Metadata generation failed.'))
    } finally {
      setIsGenerating(false)
    }
  }

  function handleMetadataSubmit(event: SubmitEvent<HTMLFormElement>) {
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

  const {
    datasetSubmitLabel,
    generatedMetadataJson,
    isEditingDataset,
    isReviewingDatasets,
    selectedDataset,
  } = metadataPageViewState({
    datasetDraft,
    editingDatasetId,
    form,
    generatedMetadata,
    isPreparingDatasets,
    selectedDatasetId,
    step,
  })

  return (
    <section className="bg-slate-100">
      <div className="mx-auto max-w-7xl px-6 py-14 md:py-18">
        <div className="mb-10">
          <h1 className="max-w-4xl text-4xl font-bold tracking-normal text-slate-950 md:text-5xl">
            Create a Metadata File for an Adapter
          </h1>
        </div>

        <div className={`grid gap-8 ${generatedMetadata ? '' : 'lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start'}`}>
          {generatedMetadata ? (
            <MetadataReadyPanel
              adapterName={form.name}
              metadata={generatedMetadata}
              metadataJson={generatedMetadataJson}
              validation={generationValidation}
              onBack={() => {
                setGeneratedMetadata(null)
                setGenerationValidation(null)
                setError(null)
                setStep(3)
              }}
            />
          ) : (
          <form className="grid gap-8" onSubmit={handleMetadataSubmit} ref={formRef}>
            <MetadataStepContent
              adapterStep={(
              <AdapterDetailsStep
                creatorActionLabel={editingCreatorId ? 'Save creator' : 'Add creator'}
                creatorDraft={creatorDraft}
                form={form}
                isEditingCreator={Boolean(editingCreatorId)}
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
              )}
              datasetBasicsStep={(
              <DatasetBasicsStep
                datasetCreatorActionLabel={editingDatasetCreatorId ? 'Save creator' : 'Add creator'}
                datasetCreatorDraft={datasetCreatorDraft}
                datasetDraft={datasetDraft}
                datasets={form.datasets}
                isEditingDatasetCreator={Boolean(editingDatasetCreatorId)}
                onAddDatasetCreator={addDatasetCreator}
                onDatasetCreatorDraftChange={(field, value) => {
                  setDatasetCreatorDraft((current) => ({ ...current, [field]: value }))
                }}
                onDatasetDraftChange={(field, value) => {
                  setDatasetDraft((current) => ({
                    ...current,
                    [field]: value,
                    uploadedDirtyFields: current.mode === 'upload'
                      ? [...new Set([...current.uploadedDirtyFields, field as typeof current.uploadedDirtyFields[number]])]
                      : current.uploadedDirtyFields,
                  }))
                }}
                onDatasetModeChange={setDatasetMode}
                onDatasetUpload={handleDatasetUpload}
                onDatasetSourceUpload={handleDatasetSourceUpload}
                onEditDatasetCreator={editDatasetCreator}
                onEditDataset={editDataset}
                onRemoveDataset={removeDataset}
                onRemoveDatasetCreator={removeDatasetCreator}
              />
              )}
              datasetDetailsStep={(
              <DatasetDetailsStep
                datasetCreatorActionLabel={editingDatasetCreatorId ? 'Save creator' : 'Add creator'}
                datasetCreatorDraft={datasetCreatorDraft}
                datasets={form.datasets}
                datasetManualField={datasetManualField}
                hideOverview={isEditingDataset}
                isEditingDatasetCreator={Boolean(editingDatasetCreatorId)}
                onAddDatasetCreator={addDatasetCreator}
                onAddManualField={addManualField}
                onDatasetCreatorDraftChange={(field, value) => {
                  setDatasetCreatorDraft((current) => ({ ...current, [field]: value }))
                }}
                onDatasetChange={updateSelectedDataset}
                onEditDatasetCreator={editDatasetCreator}
                onDistributionChange={updateSelectedDistribution}
                onFieldChange={updateSelectedField}
                onManualFieldChange={(field, value) => {
                  setDatasetManualField((current) => ({ ...current, [field]: value }))
                }}
                onRemoveDataset={removeDataset}
                onRemoveDatasetCreator={removeDatasetCreator}
                onRemoveField={removeSelectedField}
                onRecordSetNameChange={updateSelectedRecordSetName}
                onSelectDataset={(datasetId) => {
                  setError(null)
                  setSelectedDatasetId(datasetId)
                }}
                selectedDataset={selectedDataset}
                selectedDatasetId={selectedDatasetId}
              />
              )}
              isEditingDataset={isEditingDataset}
              step={step}
            />

            <MetadataFormFooter
              addDatasetAction={(
                <button
                  className="h-12 cursor-pointer rounded-lg bg-slate-200 px-5 text-base font-semibold text-slate-950 hover:bg-slate-300"
                  onClick={() => {
                    setDatasetDraft(emptyDataset)
                    setDatasetCreatorDraft(emptyCreator)
                    setEditingDatasetCreatorId(null)
                    setEditingDatasetId(null)
                    setError(null)
                    setStep(2)
                  }}
                  type="button"
                >
                  Add another dataset
                </button>
              )}
              backAction={(
                <button
                  className="h-12 rounded-lg border border-slate-200 bg-white px-5 text-base font-semibold text-slate-950 hover:border-blue-300"
                  onClick={() => {
                    setError(null)
                    setStep((current) => (current - 1) as MetadataStep)
                  }}
                  type="button"
                >
                  Back
                </button>
              )}
              capacityWait={capacityWait}
              continueAction={<button className="h-12 rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700" type="submit">Continue</button>}
              datasetAction={<button className="h-12 cursor-pointer rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400" disabled={isPreparingDatasets} type="submit">{datasetSubmitLabel}</button>}
              editingDatasetAction={(
                <div className="flex flex-wrap justify-end gap-3">
                  <button className="h-12 cursor-pointer rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400" disabled={isPreparingDatasets} onClick={(event) => {
                    if (validateDatasetDetails(event.currentTarget.form)) void prepareDatasetsForDetails(3, false, true)
                  }} type="button">{isPreparingDatasets ? 'Saving dataset...' : 'Save this dataset'}</button>
                </div>
              )}
              error={error}
              generateAction={(
                <button className="inline-flex h-12 cursor-pointer items-center justify-center gap-3 rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400" disabled={isGenerating} type="submit">
                  {isGenerating ? 'Generating...' : 'Generate adapter Croissant file'}
                  <ArrowDownTrayIcon className="h-5 w-5" aria-hidden="true" />
                </button>
              )}
              isEditingDataset={isEditingDataset}
              isReviewingDatasets={isReviewingDatasets}
              selectedDataset={selectedDataset}
              selectedDatasetAction={(
                <div className="flex flex-wrap justify-end gap-3">
                  <button className="h-12 cursor-pointer rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700" onClick={(event) => {
                    if (validateDatasetDetails(event.currentTarget.form)) setSelectedDatasetId(null)
                  }} type="button">Save this dataset</button>
                </div>
              )}
              step={step}
              warning={warning}
            />
          </form>
          )}

          {generatedMetadata ? null : <Stepper currentStep={step} />}
        </div>
      </div>
    </section>
  )
}

export function CapacityWaitPanel({ wait }: Readonly<{ wait: DatasetCapacityWait }>) {
  let message = `Your prepared dataset and form data are preserved. Retrying automatically in ${wait.retryAfterSeconds} seconds.`
  if (wait.isRetrying) {
    message = 'Retrying admission now. Your prepared dataset remains unchanged.'
  } else if (wait.attempt > 1) {
    message = `Your prepared dataset and form data are preserved. Capacity was still full after attempt ${wait.attempt}. Retrying automatically in ${wait.retryAfterSeconds} seconds.`
  }

  return (
    <div className="w-full rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950 md:min-w-96">
      <output className="block">
        <span className="block font-semibold">Generation capacity is currently full</span>
        <span className="mt-1 block">{message}</span>
      </output>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700"
          disabled={wait.isRetrying}
          onClick={wait.retryNow}
          type="button"
        >
          {wait.isRetrying ? 'Retrying…' : 'Retry now'}
        </button>
        <button
          className="rounded-lg border border-amber-400 bg-white px-4 py-2 font-semibold text-slate-950 hover:bg-amber-100"
          disabled={wait.isRetrying}
          onClick={wait.cancel}
          type="button"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

function metadataResultDescription(
  validationFailed: boolean,
  failedDatasetCount: number,
  datasetCount: number,
) {
  if (!validationFailed) {
    return 'The adapter and its datasets passed validation. Review the JSON-LD preview before downloading the final file.'
  }
  if (!failedDatasetCount) {
    return 'The adapter needs attention. Fix the failed validation before downloading or registering it.'
  }
  const datasetPhrase = datasetCount === 1 ? 'dataset needs' : 'datasets need'
  return `${failedDatasetCount} of ${datasetCount} ${datasetPhrase} attention. Fix the failed validation before downloading or registering the adapter.`
}

// Final results panel, for croissant file export
export function MetadataReadyPanel({
  adapterName,
  metadata,
  metadataJson,
  onBack,
  validation,
}: Readonly<{
  adapterName: string
  metadata: Record<string, unknown>
  metadataJson: string
  onBack: () => void
  validation: MetadataValidationResponse | null
}>) {
  const datasetCount = Array.isArray(metadata.hasPart) ? metadata.hasPart.length : 0
  const validationFailed = validation?.is_valid === false
  const downloadDisabled = validation?.is_valid !== true
  const failedDatasetCount = validation?.validation_checks?.filter(check => check.parent_id === 'datasets' && check.status === 'FAILED').length ?? 0
  const resultDescription = metadataResultDescription(validationFailed, failedDatasetCount, datasetCount)

  return (
    <section className="grid min-w-0 gap-6">
      <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm md:p-10">
        <div className="flex items-start gap-4">
          <span className={`flex h-14 w-14 flex-none items-center justify-center rounded-full ${validationFailed ? 'bg-red-100 text-red-600' : 'bg-emerald-100 text-emerald-600'}`}>
            {validationFailed ? <ExclamationTriangleIcon className="h-8 w-8" aria-hidden="true" /> : <CheckCircleIcon className="h-8 w-8" aria-hidden="true" />}
          </span>
          <div>
            <h2 className="text-2xl font-semibold text-slate-950">
              {validationFailed ? 'Adapter generated with validation errors' : 'Adapter ready'}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{resultDescription}</p>
          </div>
        </div>

        <dl className="mt-8 grid gap-4 border-t border-slate-100 pt-6 text-sm md:grid-cols-3">
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

        {validation ? <MetadataValidationPanel validation={validation} /> : null}
      </div>

      <div className="min-w-0 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="text-xl font-bold text-slate-950">JSON-LD preview</h3>
        <pre className="mt-4 max-h-96 w-full max-w-[600px] overflow-auto rounded-xl bg-slate-100 p-5 text-xs leading-5 text-slate-950">
          {metadataJson}
        </pre>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:justify-end">
          <button
            className="h-10 cursor-pointer rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-950 hover:border-blue-300"
            onClick={onBack}
            type="button"
          >
            Back to form
          </button>
          <button
            aria-describedby={downloadDisabled ? 'croissant-download-unavailable' : undefined}
            className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400 disabled:text-white"
            disabled={downloadDisabled}
            onClick={() => downloadMetadata(metadata)}
            type="button"
          >
            <ArrowDownTrayIcon className="h-5 w-5" aria-hidden="true" />
            Download finished Croissant file
          </button>
        </div>
        {downloadDisabled ? <p className="mt-3 text-right text-sm leading-6 text-red-700" id="croissant-download-unavailable">
          {validationFailed
            ? 'Download unavailable because the adapter or one of its datasets has validation errors. Fix the errors and generate it again.'
            : 'Download unavailable until validation is complete.'}
        </p> : null}
      </div>
    </section>
  )
}

function MetadataValidationPanel({ validation }: Readonly<{ validation: MetadataValidationResponse }>) {
  const detailedChecks = validation.validation_checks ?? []

  return (
    <section className="mt-8 border-t border-slate-100 pt-6" aria-label="Adapter validation report">
      {detailedChecks.length ? (
        <RegistrationValidationChecks checks={detailedChecks} />
      ) : (
        <div className="mt-5 grid gap-3">
          {validation.checks.map((check, index) => {
          const details = registrationValidationDetails({
            validation_details: [],
            validation_errors: check.errors,
          })
          return (
            <details className="rounded-xl border border-slate-200 bg-slate-50" key={`${check.name}-${index}`} open={!check.is_valid}>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3">
                <span className="font-semibold text-slate-900">{check.name}</span>
                <span className={check.is_valid ? 'text-emerald-700' : 'text-red-700'}>
                  {check.is_valid ? 'Passed' : 'Failed'}
                </span>
              </summary>
              {!check.is_valid ? (
                <div className="border-t border-slate-200 p-4">
                  <h4 className="mb-3 text-sm font-semibold text-slate-700">
                    Validation errors ({details.length})
                  </h4>
                  <DiagnosticErrors details={details} unavailableLocation />
                </div>
              ) : null}
            </details>
          )
          })}
        </div>
      )}
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
