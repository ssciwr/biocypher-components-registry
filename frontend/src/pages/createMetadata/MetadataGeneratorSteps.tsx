import type { ReactNode } from 'react'
import { DocumentArrowUpIcon, PencilSquareIcon, TrashIcon } from '@heroicons/react/24/outline'
import {
  CreatorEditor,
  DatasetDetailsEditor,
  DatasetGenerateEditor,
  FileInput,
  SelectInput,
  TextArea,
  TextInput,
} from './MetadataGeneratorFields'
import { licenseOptions } from './options'
import type {
  CreatorDraft,
  DatasetDraft,
  DatasetDatasetManualField,
  DatasetMode,
  MetadataGeneratorForm,
} from './types'

type MetadataTextField = 'adapterId'
  | 'codeRepository'
  | 'description'
  | 'keywords'
  | 'license'
  | 'name'
  | 'version'

type AdapterDetailsStepProps = Readonly<{
  creatorActionLabel: string
  creatorDraft: CreatorDraft
  form: MetadataGeneratorForm
  onAddCreator: () => void
  onCreatorDraftChange: (field: keyof CreatorDraft, value: string) => void
  onEditCreator: (id: string) => void
  onFormChange: (field: MetadataTextField, value: string) => void
  onRemoveCreator: (id: string) => void
}>

type DatasetBasicsStepProps = Readonly<{
  datasetCreatorActionLabel: string
  datasetCreatorDraft: CreatorDraft
  datasetDraft: DatasetDraft
  datasets: DatasetDraft[]
  onAddDatasetCreator: () => void
  onDatasetCreatorDraftChange: (field: keyof CreatorDraft, value: string) => void
  onDatasetDraftChange: (field: keyof DatasetDraft, value: string) => void
  onDatasetModeChange: (mode: DatasetMode) => void
  onDatasetSourceUpload: (file: File | null) => void
  onDatasetUpload: (file: File | null) => void
  onEditDatasetCreator: (id: string) => void
  onEditDataset: (id: string) => void
  onRemoveDataset: (id: string) => void
  onRemoveDatasetCreator: (id: string) => void
}>

type DatasetDetailsStepProps = Readonly<{
  datasets: DatasetDraft[]
  datasetManualField: DatasetDatasetManualField
  onAddManualField: () => void
  onDatasetChange: (field: keyof DatasetDraft, value: string) => void
  onFieldChange: (fieldId: string, field: keyof DatasetDatasetManualField, value: string) => void
  onManualFieldChange: (field: keyof DatasetDatasetManualField, value: string) => void
  onRemoveDataset: (id: string) => void
  onRemoveField: (fieldId: string) => void
  onSelectDataset: (id: string) => void
  selectedDataset: DatasetDraft | undefined
  selectedDatasetId: string | null
}>

type MetadataSectionProps = Readonly<{
  children: ReactNode
  description: string
  step: number
  title: string
}>

type SelectedItemListProps<TItem extends { id: string }> = Readonly<{
  emptyMessage: string
  getLabel: (item: TItem) => string
  getSubtitle: (item: TItem) => string
  items: TItem[]
  onEdit?: (id: string) => void
  onRemove: (id: string) => void
}>

type RemoveItemButtonProps = Readonly<{
  label: string
  onClick: () => void
}>

// First step in the process, name and other key information.
export function AdapterDetailsStep({
  creatorActionLabel,
  creatorDraft,
  form,
  onAddCreator,
  onCreatorDraftChange,
  onEditCreator,
  onFormChange,
  onRemoveCreator,
}: AdapterDetailsStepProps) {
  return (
    <MetadataSection
      description="Describe the adapter, its source code, and the people or organizations responsible for it."
      step={1}
      title="Adapter details"
    >
      <div className="mt-7 grid gap-5 md:grid-cols-2">
        <TextInput
          label="Adapter name"
          maxLength={100}
          onChange={(name) => onFormChange('name', name)}
          placeholder="Example: My Awesome BioCypher Adapter"
          required
          value={form.name}
        />
        <TextInput
          label="Adapter ID"
          maxLength={100}
          onChange={(adapterId) => onFormChange('adapterId', adapterId)}
          placeholder="my-awesome-biocypher-adapter"
          value={form.adapterId}
        />
        <TextInput
          label="Version"
          maxLength={50}
          onChange={(version) => onFormChange('version', version)}
          placeholder="Example: 0.0.1 (semantic version)"
          required
          value={form.version}
        />
        <TextInput
          label="Repository URL"
          maxLength={200}
          onChange={(codeRepository) => onFormChange('codeRepository', codeRepository)}
          placeholder="Example: https://github.com/biocypher/my-awesome-adapter"
          required
          value={form.codeRepository}
        />
        <SelectInput
          label="License"
          onChange={(license) => onFormChange('license', license)}
          options={licenseOptions}
          required
          value={form.license}
        />
        <TextInput
          label="Keywords"
          maxLength={200}
          onChange={(keywords) => onFormChange('keywords', keywords)}
          placeholder="adapter, biocypher"
          required
          value={form.keywords}
        />
      </div>
      <div className="mt-5">
        <TextArea
          label="Description"
          maxLength={800}
          onChange={(description) => onFormChange('description', description)}
          placeholder="Describe what your BioCypher adapter does..."
          required
          value={form.description}
        />
      </div>

      <div className="mt-8 grid gap-4">
        <h3 className="text-xl font-bold text-slate-950">Creators</h3>
        <SelectedItemList
          emptyMessage="No creators yet"
          getLabel={(creator) => creator.name}
          getSubtitle={(creator) => creator.creatorType}
          items={form.creators}
          onEdit={onEditCreator}
          onRemove={onRemoveCreator}
        />
        <CreatorEditor
          actionLabel={creatorActionLabel}
          draft={creatorDraft}
          onAdd={onAddCreator}
          onChange={onCreatorDraftChange}
        />
      </div>
    </MetadataSection>
  )
}

// Step 2
export function DatasetBasicsStep({
  datasetCreatorActionLabel,
  datasetCreatorDraft,
  datasetDraft,
  datasets,
  onAddDatasetCreator,
  onDatasetCreatorDraftChange,
  onDatasetDraftChange,
  onDatasetModeChange,
  onDatasetSourceUpload,
  onDatasetUpload,
  onEditDatasetCreator,
  onEditDataset,
  onRemoveDataset,
  onRemoveDatasetCreator,
}: DatasetBasicsStepProps) {
  const sourceButtonBaseClass = 'grid min-h-28 cursor-pointer gap-2 rounded-xl border p-5 text-left'
  let generateButtonClass = `${sourceButtonBaseClass} border-slate-200 bg-white text-slate-950 hover:border-blue-300`
  let uploadButtonClass = generateButtonClass
  if (datasetDraft.mode === 'generate') {
    generateButtonClass = `${sourceButtonBaseClass} border-blue-600 bg-blue-50 text-blue-700`
  }
  if (datasetDraft.mode === 'upload') {
    uploadButtonClass = `${sourceButtonBaseClass} border-blue-600 bg-blue-50 text-blue-700`
  }

  return (
    <MetadataSection
      description="Add each dataset, either by uploading source data to generate Croissant metadata or uploading an existing dataset Croissant file."
      step={2}
      title="Basic dataset info"
    >
      <div className="mt-7 grid gap-4">
        <DatasetOverviewTable
          datasets={datasets}
          emptyMessage="No datasets added yet"
          onEdit={onEditDataset}
          onRemove={onRemoveDataset}
        />

        <div className="grid gap-4 md:grid-cols-2">
          <button
            className={generateButtonClass}
            onClick={() => onDatasetModeChange('generate')}
            type="button"
          >
            <span className="text-base font-bold">
              I need to generate a Croissant file for the dataset too
            </span>
            <span className="text-sm leading-6 text-slate-600">
              Select a source data file from this computer so the backend can create dataset Croissant metadata.
            </span>
          </button>
          <button
            className={uploadButtonClass}
            onClick={() => onDatasetModeChange('upload')}
            type="button"
          >
            <span className="text-base font-bold">Upload existing dataset Croissant file</span>
            <span className="text-sm leading-6 text-slate-600">
              Select a Croissant JSON-LD file from this computer and embed its metadata in the adapter.
            </span>
          </button>
        </div>

        {datasetDraft.mode === 'generate' ? (
          <>
            <DatasetGenerateEditor
              draft={datasetDraft}
              licenseOptions={licenseOptions}
              onChange={onDatasetDraftChange}
              onSourceFileChange={onDatasetSourceUpload}
              sourceRequired={!datasets.length}
            />
            <div className="grid gap-4">
              <h3 className="text-xl font-bold text-slate-950">Dataset creators</h3>
              <SelectedItemList
                emptyMessage="No creators yet"
                getLabel={(creator) => creator.name}
                getSubtitle={(creator) => creator.creatorType}
                items={datasetDraft.creators}
                onEdit={onEditDatasetCreator}
                onRemove={onRemoveDatasetCreator}
              />
              <CreatorEditor
                actionLabel={datasetCreatorActionLabel}
                draft={datasetCreatorDraft}
                onAdd={onAddDatasetCreator}
                onChange={onDatasetCreatorDraftChange}
              />
            </div>
          </>
        ) : (
          <div className="grid gap-4 rounded-xl border border-slate-200 bg-slate-50 p-5">
            <FileInput
              accept=".json,.jsonld,application/json,application/ld+json"
              label="Dataset Croissant file"
              onChange={onDatasetUpload}
              required={!datasets.length}
            />
            {datasetDraft.uploadedFileName ? (
              <p className="inline-flex w-fit items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-700">
                <DocumentArrowUpIcon className="h-4 w-4" aria-hidden="true" />
                {datasetDraft.uploadedFileName}
              </p>
            ) : null}
          </div>
        )}
      </div>
    </MetadataSection>
  )
}

// Step 3, within this step the user toggles between datasets from Step 2 (it does not occur "for each" step 2 dataset)
export function DatasetDetailsStep({
  datasets,
  datasetManualField,
  onAddManualField,
  onDatasetChange,
  onFieldChange,
  onManualFieldChange,
  onRemoveDataset,
  onRemoveField,
  onSelectDataset,
  selectedDataset,
  selectedDatasetId,
}: DatasetDetailsStepProps) {
  return (
    <MetadataSection
      description="Select a dataset, confirm distribution metadata, and adjust detected fields before the adapter Croissant export."
      step={3}
      title="Dataset details"
    >
      <div className="mt-7 grid gap-6">
        <DatasetOverviewTable
          datasets={datasets}
          onEdit={onSelectDataset}
          onRemove={onRemoveDataset}
          selectedDatasetId={selectedDatasetId}
        />
        {selectedDataset ? (
          <DatasetDetailsEditor
            dataset={selectedDataset}
            datasetManualField={datasetManualField}
            licenseOptions={licenseOptions}
            onAddManualField={onAddManualField}
            onChange={onDatasetChange}
            onFieldChange={onFieldChange}
            onManualFieldChange={onManualFieldChange}
            onRemoveField={onRemoveField}
          />
        ) : null}
      </div>
    </MetadataSection>
  )
}


// CSS / pure-fucntion wrapper for the white form blocks that are repeated in the UI/form.
function MetadataSection({ children, description, step, title }: MetadataSectionProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-7 shadow-sm md:p-8">
      <div className="flex items-start gap-4">
        <span className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-slate-950 text-sm font-bold text-white">
          {step}
        </span>
        <span>
          <h2 className="text-2xl font-bold text-slate-950">{title}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {description}
          </p>
        </span>
      </div>
      {children}
    </section>
  )
}

// For selects like License select.
function SelectedItemList<TItem extends { id: string }>({
  emptyMessage,
  getLabel,
  getSubtitle,
  items,
  onEdit,
  onRemove,
}: SelectedItemListProps<TItem>) {
  if (!items.length) {
    return (
      <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        {emptyMessage}
      </p>
    )
  }

  return (
    <ul className="grid gap-3">
      {items.map((item) => {
        const label = getLabel(item)

        return (
          <li
            className="flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm"
            key={item.id}
          >
            <span>
              <span className="block font-semibold text-slate-950">{label}</span>
              <span className="mt-1 block text-slate-500">{getSubtitle(item)}</span>
            </span>
            <span className="flex gap-2">
              {onEdit ? (
                <button
                  className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-blue-200 px-3 text-sm font-semibold text-blue-700 hover:border-blue-400 hover:bg-blue-50"
                  onClick={() => onEdit(item.id)}
                  type="button"
                >
                  <PencilSquareIcon className="h-4 w-4" aria-hidden="true" />
                  Edit
                </button>
              ) : null}
              <RemoveItemButton label={label} onClick={() => onRemove(item.id)} />
            </span>
          </li>
        )
      })}
    </ul>
  )
}


function DatasetOverviewTable({
  datasets,
  emptyMessage,
  onEdit,
  onRemove,
  selectedDatasetId,
}: Readonly<{
  datasets: DatasetDraft[]
  emptyMessage?: string
  onEdit?: (id: string) => void
  onRemove: (id: string) => void
  selectedDatasetId?: string | null
}>) {
  if (!datasets.length) {
    return (
      <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        {emptyMessage ?? 'No datasets yet'}
      </p>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
          <tr>
            <th className="px-4 py-3">Dataset</th>
            <th className="px-4 py-3">Description</th>
            <th className="px-4 py-3">Source</th>
            <th className="px-4 py-3">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {datasets.map((dataset) => {
            let rowClass = 'bg-white'
            if (dataset.id === selectedDatasetId) {
              rowClass = 'bg-blue-50'
            }
            let sourceDetail = dataset.input ? `Source: ${dataset.input}` : 'Generate dataset Croissant'
            if (dataset.mode === 'upload') {
              sourceDetail = dataset.uploadedFileName
                ? `Croissant file: ${dataset.uploadedFileName}`
                : 'Croissant file upload'
            }

            return (
              <tr className={rowClass} key={dataset.id}>
                <td className="px-4 py-3 font-semibold text-slate-950">
                  {datasetLabel(dataset)}
                </td>
                <td className="max-w-md px-4 py-3 text-slate-700">
                  {dataset.description || 'No description yet'}
                </td>
                <td className="px-4 py-3 text-slate-700">
                  <span className="inline-flex rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                    {dataset.mode === 'upload' ? 'Croissant file' : 'Sample file'}
                  </span>
                  <span className="mt-1 block text-xs text-slate-500">
                    {sourceDetail}
                  </span>
                </td>
                <td className="flex gap-2 px-4 py-3">
                  {onEdit ? (
                    <button
                      className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-blue-200 px-3 text-sm font-semibold text-blue-700 hover:border-blue-400 hover:bg-blue-50"
                      onClick={() => onEdit(dataset.id)}
                      type="button"
                    >
                      <PencilSquareIcon className="h-4 w-4" aria-hidden="true" />
                      Edit
                    </button>
                  ) : null}
                  <RemoveItemButton
                    label={datasetLabel(dataset)}
                    onClick={() => onRemove(dataset.id)}
                  />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function RemoveItemButton({ label, onClick }: RemoveItemButtonProps) {
  return (
    <button
      aria-label={`Remove ${label}`}
      className="inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:border-red-200 hover:text-red-600"
      onClick={onClick}
      type="button"
    >
      <TrashIcon className="h-4 w-4" aria-hidden="true" />
    </button>
  )
}

function datasetLabel(dataset: DatasetDraft) {
  return dataset.name || dataset.uploadedFileName || dataset.input || 'Untitled dataset'
}
