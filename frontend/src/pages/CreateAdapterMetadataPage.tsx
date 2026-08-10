import { useState, type ReactNode } from 'react'
import {
  ArrowDownTrayIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import { generateAdapterMetadataApiV1MetadataAdaptersGeneratePost } from '../api/client'
import {
  CreatorEditor,
  DatasetEditor,
  SelectInput,
  TextArea,
  TextInput,
} from './createMetadata/MetadataGeneratorFields'
import {
  emptyCreator,
  emptyDataset,
  emptyForm,
  licenseOptions,
} from './createMetadata/options'
import type { CreatorDraft, DatasetDraft, MetadataGeneratorForm } from './createMetadata/types'
import {
  creatorToApiValue,
  datasetPathsToApiValues,
  downloadMetadata,
  errorText,
  generatedDatasetsToApiValues,
  keywordsToApiValues,
  nextDraftId,
  optionalValue,
} from './createMetadata/utils'

type MetadataSectionProps = Readonly<{
  children: ReactNode
  description: string
  step: number
  title: string
}>

type RemoveItemButtonProps = Readonly<{
  label: string
  onClick: () => void
}>

type SelectedItemListProps<TItem extends { id: string }> = Readonly<{
  emptyMessage: string
  getLabel: (item: TItem) => string
  getSubtitle: (item: TItem) => string
  items: TItem[]
  onRemove: (id: string) => void
}>

// for input reuse
function MetadataSection({ children, description, step, title }: MetadataSectionProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-7 shadow-sm md:p-8">
      <div className="flex items-start gap-4">
        <span className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-blue-100 text-sm font-bold text-blue-600">
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

// this is used in multiple places so this just saves CSS
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

// resuable UI component again, possibly refactor this and the above out together into a "reusable UI" file.
function SelectedItemList<TItem extends { id: string }>({
  emptyMessage,
  getLabel,
  getSubtitle,
  items,
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
            <RemoveItemButton label={label} onClick={() => onRemove(item.id)} />
          </li>
        )
      })}
    </ul>
  )
}

function CreateAdapterMetadataPage() {
  const [form, setForm] = useState<MetadataGeneratorForm>(emptyForm)
  const [creatorDraft, setCreatorDraft] = useState<CreatorDraft>(emptyCreator)
  const [datasetDraft, setDatasetDraft] = useState<DatasetDraft>(emptyDataset)
  const [error, setError] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)

// Creators. this interface will be extracted out to also work with dataset creators.
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


  function addDataset() {
    // prevent rows that cannot become a valid API dataset payload.
    if (datasetDraft.mode === 'croissant' && !datasetDraft.path.trim()) {
      setError('Add a Croissant file path first.')
      return
    }

    if (datasetDraft.mode === 'manual' && !datasetDraft.input.trim()) {
      setError('Add an input path first.')
      return
    }

    setForm((current) => ({
      ...current,
      datasets: [...current.datasets, { ...datasetDraft, id: nextDraftId('dataset') }],
    }))
    setDatasetDraft(emptyDataset)
    setError(null)
  }

  function removeDataset(id: string) {
    setForm((current) => ({
      ...current,
      datasets: current.datasets.filter((dataset) => dataset.id !== id),
    }))
  }

 // the main/core function. flow will change slightly soon with step 2/3/4 full implementation
  async function generateMetadata(event: { preventDefault: () => void }) {
    event.preventDefault()

    const creators = form.creators.map(creatorToApiValue)
    const keywords = keywordsToApiValues(form.keywords)
    // below here is based on temporary code we will replace shortly with true/full impelmentation and GUI design,
    // currently this just passes attributes through without exposing on the frontend.
    const datasetPaths = datasetPathsToApiValues(form.datasets)
    const generatedDatasets = generatedDatasetsToApiValues(form.datasets)

    if (!creators.length) {
      setError('Add at least one adapter creator.')
      return
    }

    if (!keywords.length) {
      setError('Add at least one keyword.')
      return
    }

    if (!datasetPaths.length && !generatedDatasets.length) {
      setError('Add at least one Croissant file path or manual dataset.')
      return
    }

    setError(null)
    setIsGenerating(true)
    try {
      const result = await generateAdapterMetadataApiV1MetadataAdaptersGeneratePost({
        body: {
          adapter_id: optionalValue(form.adapterId),
          code_repository: form.codeRepository,
          creators,
          dataset_paths: datasetPaths,
          generated_datasets: generatedDatasets,
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

      downloadMetadata(result.data.metadata, form.name)
      setError(null)
    } catch (error) {
      setError(errorText(error, 'Metadata generation failed.'))
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <section className="bg-slate-100">
      <div className="mx-auto max-w-7xl px-6 py-14 md:py-18">
        <div className="mb-10">
          <a className="text-sm font-semibold text-blue-600 hover:text-blue-700" href="/create">
            Create
          </a>
          <h1 className="mt-4 max-w-4xl text-4xl font-bold tracking-normal text-slate-950 md:text-5xl">
            Create a Metadata File for an Adapter
          </h1>
        </div>

        <form className="grid gap-8" onSubmit={generateMetadata}>
          <div className="grid gap-8">
            <MetadataSection
              description="Describe the adapter and where its source code lives."
              step={1}
              title="Adapter details"
            >
              <div className="mt-7 grid gap-5 md:grid-cols-2">
                <TextInput
                  label="Adapter name"
                  maxLength={100}
                  onChange={(name) => setForm((current) => ({ ...current, name }))}
                  placeholder="Example: My Awesome BioCypher Adapter"
                  required
                  value={form.name}
                />
                <TextInput
                  label="Adapter ID"
                  maxLength={100}
                  onChange={(adapterId) => setForm((current) => ({ ...current, adapterId }))}
                  placeholder="my-awesome-biocypher-adapter"
                  value={form.adapterId}
                />
                <TextInput
                  label="Version"
                  maxLength={50}
                  onChange={(version) => setForm((current) => ({ ...current, version }))}
                  placeholder="Example: 0.0.1 (semantic version)"
                  required
                  value={form.version}
                />
                <TextInput
                  label="Repository URL"
                  maxLength={200}
                  onChange={(codeRepository) => setForm((current) => ({ ...current, codeRepository }))}
                  placeholder="Example: https://github.com/biocypher/my-awesome-adapter"
                  required
                  value={form.codeRepository}
                />
                <SelectInput
                  label="License"
                  onChange={(license) => setForm((current) => ({ ...current, license }))}
                  options={licenseOptions}
                  required
                  value={form.license}
                />
                <TextInput
                  label="Keywords"
                  maxLength={200}
                  onChange={(keywords) => setForm((current) => ({ ...current, keywords }))}
                  placeholder="adapter, biocypher"
                  required
                  value={form.keywords}
                />
              </div>
              <div className="mt-5">
                <TextArea
                  label="Description"
                  maxLength={800}
                  onChange={(description) => setForm((current) => ({ ...current, description }))}
                  placeholder="Describe what your BioCypher adapter does..."
                  required
                  value={form.description}
                />
              </div>
            </MetadataSection>

            <MetadataSection
              description="Add the people or organizations responsible for this adapter."
              step={2}
              title="Adapter creators"
            >
              <div className="mt-7 grid gap-4">
                <SelectedItemList
                  emptyMessage="No creators yet"
                  getLabel={(creator) => creator.name}
                  getSubtitle={(creator) => creator.creatorType}
                  items={form.creators}
                  onRemove={removeCreator}
                />
                <CreatorEditor
                  draft={creatorDraft}
                  onAdd={addCreator}
                  onChange={(field, value) => {
                    setCreatorDraft((current) => ({ ...current, [field]: value }))
                  }}
                />
              </div>
            </MetadataSection>

            <MetadataSection
              description="Add existing dataset Croissant files or generate embedded dataset metadata."
              step={3}
              title="Datasets"
            >
              <div className="mt-7 grid gap-4">
                <SelectedItemList
                  emptyMessage="No datasets yet"
                  getLabel={(dataset) => (
                    dataset.mode === 'croissant' ? dataset.path : dataset.name || dataset.input
                  )}
                  getSubtitle={(dataset) => (
                    dataset.mode === 'croissant' ? 'Croissant file path' : 'Manual dataset information'
                  )}
                  items={form.datasets}
                  onRemove={removeDataset}
                />
                <DatasetEditor
                  draft={datasetDraft}
                  licenseOptions={licenseOptions}
                  onAdd={addDataset}
                  onChange={(field, value) => {
                    setDatasetDraft((current) => ({ ...current, [field]: value }))
                  }}
                />
              </div>
            </MetadataSection>
          </div>

          <div className="flex flex-col gap-4 border-t border-slate-200 pt-8 md:items-end">
            {error ? (
              <p className="w-full rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </p>
            ) : null}
            <button
              className="inline-flex h-14 w-full cursor-pointer items-center justify-center gap-3 rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400 md:w-fit"
              disabled={isGenerating}
              type="submit"
            >
              {isGenerating ? 'Generating...' : 'Export croissant file'}
              <ArrowDownTrayIcon className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </form>
      </div>
    </section>
  )
}

export default CreateAdapterMetadataPage
