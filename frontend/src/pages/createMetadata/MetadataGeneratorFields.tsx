import { useEffect, useId, useRef, useState } from 'react'
import { DocumentArrowUpIcon, DocumentCheckIcon, DocumentIcon, FolderIcon, PlusIcon, QuestionMarkCircleIcon, TrashIcon } from '@heroicons/react/24/outline'
import type {
  CreatorDraft,
  CreatorType,
  DatasetDatasetManualField,
  DatasetDraft,
  DatasetSourceSelection,
  SelectOption,
} from './types'
import { citationTextFromBibtexFile } from './citation'
import { selectionFromFile, selectionFromFolderFiles } from './datasetSourceSelection'
import { normaliseOrcid } from './utils'

type TextInputProps = Readonly<{
  fillHeight?: boolean
  helpText?: string
  inputType?: 'date' | 'text'
  label: string
  maxLength?: number
  name?: string
  onChange: (value: string) => void
  placeholder?: string
  readOnly?: boolean
  required?: boolean
  surface?: 'muted' | 'plain'
  value: string
}>

type TextAreaProps = Readonly<TextInputProps>

type FileInputProps = Readonly<{
  accept?: string
  label: string
  onChange: (file: File | null) => void
  required?: boolean
}>

type SelectInputProps<TValue extends string> = Readonly<{
  helpText?: string
  label: string
  onChange: (value: TValue) => void
  options: ReadonlyArray<SelectOption<TValue>>
  required?: boolean
  surface?: 'muted' | 'plain'
  value: TValue
}>

type CreatorEditorProps = Readonly<{
  actionLabel: string
  draft: CreatorDraft
  isEditing?: boolean
  nameInputName?: string
  onAdd: () => void
  onChange: (field: keyof CreatorDraft, value: string) => void
}>

type DatasetGenerateEditorProps = Readonly<{
  draft: DatasetDraft
  licenseOptions: SelectOption[]
  onChange: (field: keyof DatasetDraft, value: string) => void
  onSourceFileChange: (selection: DatasetSourceSelection | null) => void
  requirePublicationFields?: boolean
  showDistribution?: boolean
  showSource?: boolean
  sourceRequired?: boolean
}>

type DatasetSourceInputProps = Readonly<{
  onChange: (selection: DatasetSourceSelection | null) => void
  required?: boolean
}>

type DatasetDetailsEditorProps = Readonly<{
  dataset: DatasetDraft
  datasetManualField: DatasetDatasetManualField
  licenseOptions: SelectOption[]
  onAddManualField: (recordSetIndex?: number) => void
  onChange: (field: keyof DatasetDraft, value: string) => void
  onDistributionChange: (
    distributionIndex: number,
    field: 'contentUrl' | 'encodingFormat' | 'filename' | 'md5' | 'sha256',
    value: string,
  ) => void
  onFieldChange: (recordSetIndex: number | undefined, fieldId: string, field: keyof DatasetDatasetManualField, value: string) => void
  onManualFieldChange: (field: keyof DatasetDatasetManualField, value: string) => void
  onRemoveField: (recordSetIndex: number | undefined, fieldId: string) => void
  onRecordSetNameChange: (recordSetIndex: number, value: string) => void
}>

type LicenseSelectInputProps = Readonly<{
  helpText?: string
  label?: string
  licenseOptions: SelectOption[]
  onChange: (value: string) => void
  required?: boolean
  surface?: 'muted' | 'plain'
  value: string
}>

const creatorTypeOptions: ReadonlyArray<SelectOption<CreatorType>> = [
  { label: 'Person', value: 'Person' },
  { label: 'Organization', value: 'Organization' },
]

const fieldDataTypeOptions: ReadonlyArray<SelectOption<string>> = [
  { disabled: true, label: '(None)', value: '' },
  { label: 'sc:Text', value: 'sc:Text' },
  { label: 'sc:Integer', value: 'sc:Integer' },
  { label: 'sc:Float', value: 'sc:Float' },
  { label: 'sc:Boolean', value: 'sc:Boolean' },
  { label: 'sc:Date', value: 'sc:Date' },
  { label: 'sc:URL', value: 'sc:URL' },
]

export const datasetMetadataSectionId = 'dataset-metadata-section'


// TODO: Review whether a UI library such as shadcn should replace the custom controls. // NOSONAR
/** Backlog detail:
 *  Should review whether we should actually use a UI library like shadcn because the custom coding is extra code
 *  and is beginning not to make sense.
 */

function HelpTooltip({ label, children }: Readonly<{ label: string; children: string }>) {
  const helpId = useId()
  return (
    <button
      aria-describedby={helpId}
      aria-label={`Help for ${label}`}
      className="group relative inline-flex cursor-help border-0 bg-transparent p-0 text-slate-500 outline-none"
      type="button"
    >
      <QuestionMarkCircleIcon className="h-4 w-4" aria-hidden="true" />
      <span
        className="invisible absolute bottom-full left-1/2 z-20 mb-2 w-64 -translate-x-1/2 rounded-lg bg-slate-950 px-3 py-2 text-xs font-normal leading-5 text-white opacity-0 shadow-lg transition group-hover:visible group-hover:opacity-100 group-focus:visible group-focus:opacity-100"
        id={helpId}
        role="tooltip"
      >
        {children}
      </span>
    </button>
  )
}

export function TextInput({
  helpText,
  inputType = 'text',
  label,
  maxLength,
  name,
  onChange,
  placeholder,
  readOnly = false,
  required = false,
  surface = 'muted',
  value,
}: TextInputProps) {
  let backgroundClass = 'bg-slate-50 focus:bg-white'
  if (surface === 'plain') {
    backgroundClass = 'bg-white'
  }

  return (
    <label className="grid min-w-0 gap-2 text-sm font-semibold text-slate-950">
      <span className="flex items-center gap-1.5">
        <span>{label}{required ? ' *' : ''}</span>
        {helpText ? (
          <HelpTooltip label={label}>{helpText}</HelpTooltip>
        ) : null}
      </span>
      <input
        className={`h-12 w-full min-w-0 rounded-xl border border-slate-200 px-4 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 read-only:cursor-default read-only:bg-slate-100 read-only:text-slate-600 ${backgroundClass}`}
        maxLength={maxLength}
        name={name}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        readOnly={readOnly}
        required={required}
        type={inputType}
        value={value}
      />
    </label>
  )
}

export function TextArea({
  fillHeight = false,
  helpText,
  label,
  maxLength,
  onChange,
  placeholder,
  required = false,
  surface = 'muted',
  value,
}: TextAreaProps) {
  let backgroundClass = 'bg-slate-50 focus:bg-white'
  if (surface === 'plain') {
    backgroundClass = 'bg-white'
  }

  return (
    <label className={`grid min-w-0 gap-2 text-sm font-semibold text-slate-950 ${fillHeight ? 'h-full grid-rows-[auto_minmax(0,1fr)]' : ''}`}>
      <span className="flex items-center gap-1.5">
        <span>{label}{required ? ' *' : ''}</span>
        {helpText ? (
          <HelpTooltip label={label}>{helpText}</HelpTooltip>
        ) : null}
      </span>
      <textarea
        className={`min-h-28 w-full min-w-0 rounded-xl border border-slate-200 px-4 py-3 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 ${fillHeight ? 'h-full resize-none' : ''} ${backgroundClass}`}
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        value={value}
      />
    </label>
  )
}

function CitationInput({
  fillHeight = false,
  onChange,
  surface = 'muted',
  value,
}: Readonly<{
  fillHeight?: boolean
  onChange: (value: string) => void
  surface?: 'muted' | 'plain'
  value: string
}>) {
  const citationId = useId()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [importError, setImportError] = useState<string | null>(null)
  const backgroundClass = surface === 'plain' ? 'bg-white' : 'bg-slate-50 focus:bg-white'
  const containsBibtex = value.trimStart().startsWith('@')

  async function importBibtex(file: File | undefined) {
    if (!file) return
    try {
      onChange(await citationTextFromBibtexFile(file))
      setImportError(null)
    } catch (error) {
      setImportError(error instanceof Error ? error.message : 'Could not import the BibTeX file.')
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className={`grid min-w-0 gap-2 text-sm font-semibold text-slate-950 ${fillHeight ? 'h-full grid-rows-[auto_minmax(0,1fr)]' : ''}`}>
      <div className="relative min-w-0 pr-32">
        <span className="flex items-center gap-1.5">
          <label htmlFor={citationId}>Citation</label>
          <HelpTooltip label="Citation">
            Citation for this dataset. Paste formatted citation text, enter BibTeX, or import a .bib file.
          </HelpTooltip>
        </span>
        <button
          aria-label="Import BibTeX file"
          className="absolute right-0 top-1/2 inline-flex h-7 -translate-y-1/2 cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-2 text-xs font-semibold text-slate-700 hover:border-blue-400 hover:text-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
          onClick={() => fileInputRef.current?.click()}
          type="button"
        >
          <DocumentArrowUpIcon className="h-4 w-4" aria-hidden="true" />
          Import BibTeX
        </button>
      </div>
      <textarea
        aria-describedby={importError ? `${citationId}-error` : undefined}
        className={`min-h-28 w-full min-w-0 rounded-xl border border-slate-200 px-4 py-3 text-left text-sm font-normal leading-6 text-slate-950 outline-none placeholder:font-sans placeholder:text-slate-500 focus:border-blue-500 ${containsBibtex ? 'font-mono' : 'font-sans'} ${fillHeight ? 'h-full resize-none' : ''} ${backgroundClass}`}
        id={citationId}
        maxLength={10_000}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Paste a citation or BibTeX entry"
        spellCheck={!containsBibtex}
        value={value}
      />
      <input
        accept=".bib,application/x-bibtex,text/x-bibtex"
        aria-label="Citation BibTeX file"
        className="hidden"
        onChange={(event) => void importBibtex(event.target.files?.[0])}
        ref={fileInputRef}
        type="file"
      />
      {importError ? <p className="text-xs text-red-700" id={`${citationId}-error`} role="alert">{importError}</p> : null}
    </div>
  )
}

export function SelectInput<TValue extends string>({
  helpText,
  label,
  onChange,
  options,
  required = false,
  surface = 'muted',
  value,
}: SelectInputProps<TValue>) {
  let backgroundClass = 'bg-slate-50 focus:bg-white'
  if (surface === 'plain') {
    backgroundClass = 'bg-white'
  }

  return (
    <label className="grid min-w-0 gap-2 text-sm font-semibold text-slate-950">
      <span className="flex items-center gap-1.5">
        <span>{label}{required ? ' *' : ''}</span>
        {helpText ? (
          <HelpTooltip label={label}>{helpText}</HelpTooltip>
        ) : null}
      </span>
      <select
        className={`h-12 w-full min-w-0 rounded-xl border border-slate-200 px-4 text-base font-normal text-slate-950 outline-none focus:border-blue-500 ${backgroundClass}`}
        onChange={(event) => onChange(event.target.value as TValue)}
        required={required}
        value={value}
      >
        {options.map((option) => (
          <option disabled={option.disabled} key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

/*
 * AI-Generated.
 */
export function LicenseSelectInput({
  helpText = 'License under which the dataset is made available. Select the license assigned by its owner or publisher.',
  label = 'License',
  licenseOptions,
  onChange,
  required = false,
  surface = 'muted',
  value,
}: LicenseSelectInputProps) {
  return (
    <SelectInput
      helpText={helpText}
      label={label}
      onChange={onChange}
      options={licenseOptions}
      required={required}
      surface={surface}
      value={value}
    />
  )
}

export function FileInput({
  accept,
  label,
  onChange,
  required = false,
}: FileInputProps) {
  return (
    <label className="grid gap-2 text-sm font-semibold text-slate-950">
      <span>{label}{required ? ' *' : ''}</span>
      <input
        accept={accept}
        className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-3 text-sm font-normal text-slate-700 file:mr-4 file:cursor-pointer file:rounded-lg file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-blue-700"
        onChange={(event) => onChange(event.target.files?.item(0) ?? null)}
        required={required}
        type="file"
      />
    </label>
  )
}

function DatasetSourceInput({ onChange, required = false }: DatasetSourceInputProps) {
  const pickerRoot = useRef<HTMLDivElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [selectionError, setSelectionError] = useState<string | null>(null)

  useEffect(() => {
    folderInput.current?.setAttribute('webkitdirectory', '')
  }, [])

  useEffect(() => {
    if (!pickerOpen) return

    function closeOnOutsideClick(event: MouseEvent) {
      if (!pickerRoot.current?.contains(event.target as Node)) setPickerOpen(false)
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setPickerOpen(false)
    }
    globalThis.document.addEventListener('mousedown', closeOnOutsideClick)
    globalThis.document.addEventListener('keydown', closeOnEscape)
    return () => {
      globalThis.document.removeEventListener('mousedown', closeOnOutsideClick)
      globalThis.document.removeEventListener('keydown', closeOnEscape)
    }
  }, [pickerOpen])

  function openFilePicker() {
    setPickerOpen(false)
    fileInput.current?.click()
  }

  function openFolderPicker() {
    setPickerOpen(false)
    folderInput.current?.click()
  }

  return (
    <div className="grid gap-2 text-sm font-semibold text-slate-950">
      <span className="flex items-center gap-1.5">
        <span>Source dataset file or folder{required ? ' *' : ''}</span>
        <HelpTooltip label="Source dataset file or folder">
          UTF-8 CSV/TSV and Gzip-compressed CSV/TSV are supported. Large or compressed files are sampled in your browser; source data is never retained.
        </HelpTooltip>
      </span>
      <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-4 text-sm font-normal text-slate-700">
        <div className="relative w-fit" ref={pickerRoot}>
        <button
          aria-expanded={pickerOpen}
          aria-haspopup="menu"
          className="cursor-pointer rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700"
          onClick={() => setPickerOpen((open) => !open)}
          type="button"
        >
          Browse source…
        </button>
        {pickerOpen ? (
          <div
            aria-label="Dataset source type"
            className="absolute left-0 top-full z-20 mt-2 min-w-52 overflow-hidden rounded-xl border border-slate-200 bg-white p-1 shadow-lg"
            role="menu"
          >
            <button
              className="flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-slate-800 hover:bg-blue-50"
              onClick={openFilePicker}
              role="menuitem"
              type="button"
            >
              <DocumentIcon className="h-5 w-5 text-blue-600" aria-hidden="true" />
              Select one file
            </button>
            <button
              className="flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-slate-800 hover:bg-blue-50"
              onClick={openFolderPicker}
              role="menuitem"
              type="button"
            >
              <FolderIcon className="h-5 w-5 text-blue-600" aria-hidden="true" />
              Select one folder
            </button>
          </div>
        ) : null}
        </div>
        <input
          accept=".csv,.tsv,.csv.gz,.tsv.gz,text/csv,text/tab-separated-values,application/gzip"
          aria-label="Source dataset file"
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.item(0)
            onChange(file ? selectionFromFile(file) : null)
            setSelectionError(null)
            event.target.value = ''
          }}
          ref={fileInput}
          type="file"
        />
        <input
          aria-label="Source dataset folder"
          className="sr-only"
          onChange={(event) => {
            try {
              onChange(event.target.files ? selectionFromFolderFiles(event.target.files) : null)
              setSelectionError(null)
            } catch (error) {
              onChange(null)
              setSelectionError(error instanceof Error ? error.message : 'Could not read the selected folder.')
            }
            event.target.value = ''
          }}
          multiple
          ref={folderInput}
          type="file"
        />
      </div>
      {selectionError ? <p className="text-xs font-normal text-red-700" role="alert">{selectionError}</p> : null}
    </div>
  )
}

export function CreatorEditor({
  actionLabel,
  draft,
  isEditing = false,
  nameInputName,
  onAdd,
  onChange,
}: CreatorEditorProps) {
  const ActionIcon = isEditing ? DocumentCheckIcon : null

  return (
    <div className="grid gap-4 rounded-xl border border-slate-200 bg-slate-50 p-5">
      <div className="grid gap-4 md:grid-cols-2">
        <TextInput
          label="Name"
          maxLength={100}
          name={nameInputName}
          onChange={(value) => onChange('name', value)}
          placeholder="Example: Robert Koch"
          surface="plain"
          value={draft.name}
        />
        <SelectInput
          label="Creator type"
          onChange={(value) => onChange('creatorType', value)}
          options={creatorTypeOptions}
          surface="plain"
          value={draft.creatorType}
        />
      </div>
      <TextInput
        label="Affiliation(s) (comma-separated)"
        maxLength={100}
        onChange={(value) => onChange('affiliation', value)}
        placeholder="Example: Robert Koch Institute, University of Goettingen"
        surface="plain"
        value={draft.affiliation}
      />
      <div className="grid gap-4 md:grid-cols-2">
        <TextInput
          label="ORCID ID"
          onChange={(value) => onChange('orcid', normaliseOrcid(value))}
          placeholder="Example: https://orcid.org/1234-5678-9101-1121"
          surface="plain"
          value={draft.orcid}
        />
        <TextInput
          label="Email"
          maxLength={100}
          onChange={(value) => onChange('email', value)}
          placeholder="Example: robert.koch@rki.de-mail.de"
          surface="plain"
          value={draft.email}
        />
      </div>
      <TextInput
        label="URL"
        maxLength={200}
        onChange={(value) => onChange('url', value)}
        placeholder="Example: www.rki.de"
        surface="plain"
        value={draft.url}
      />
      <div className="flex justify-end">
        <button
          className="inline-flex h-11 w-fit cursor-pointer items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 text-sm font-semibold text-white hover:bg-blue-700"
          onClick={onAdd}
          type="button"
        >
          {ActionIcon ? <ActionIcon className="h-4 w-4" aria-hidden="true" /> : null}
          {actionLabel}
        </button>
      </div>
    </div>
  )
}

//  For editing the dataset
export function DatasetGenerateEditor({
  draft,
  licenseOptions,
  onChange,
  onSourceFileChange,
  requirePublicationFields = true,
  showDistribution = true,
  showSource = true,
  sourceRequired = false,
}: DatasetGenerateEditorProps) {
  return (
    <div className="grid gap-4 rounded-xl border border-slate-200 bg-slate-50 p-5">
      {showSource ? <DatasetSourceInput onChange={onSourceFileChange} required={sourceRequired} /> : null}
      {showSource && draft.sourceFileName ? (
        <p className="inline-flex w-fit items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-700">
          <DocumentArrowUpIcon className="h-4 w-4" aria-hidden="true" />
          {draft.sourceFileName}
        </p>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        <TextInput
          helpText="Clear, human-readable title that helps people identify the dataset."
          label="Dataset name"
          maxLength={100}
          onChange={(value) => onChange('name', value)}
          placeholder="Example Dataset"
          surface="plain"
          value={draft.name}
        />
        <LicenseSelectInput
          licenseOptions={licenseOptions}
          onChange={(value) => onChange('license', value)}
          surface="plain"
          value={draft.license}
        />
      </div>
      <TextArea
        label="Description"
        maxLength={requirePublicationFields ? 500 : undefined}
        onChange={(value) => onChange('description', value)}
        placeholder="Small people dataset."
        surface="plain"
        value={draft.description}
      />
      <div className="grid items-stretch gap-4 md:grid-cols-2">
        <div className="grid gap-4">
          <TextInput
            helpText="Public dataset landing or information page URL."
            label="Dataset landing page"
            maxLength={200}
            onChange={(value) => onChange('url', value)}
            placeholder="https://example.org/people"
            surface="plain"
            value={draft.url}
          />
          <TextInput
            helpText="Version identifier for this dataset release. Semantic versions such as 1.0.0 are recommended, but other versioning schemes are accepted."
            label="Dataset version"
            maxLength={50}
            onChange={(value) => onChange('datasetVersion', value)}
            placeholder="0.0.1"
            required={requirePublicationFields}
            surface="plain"
            value={draft.datasetVersion}
          />
          <TextInput
            inputType="date"
            label="Date published"
            maxLength={20}
            onChange={(value) => onChange('datePublished', value)}
            placeholder="2026-04-17"
            required={requirePublicationFields}
            surface="plain"
            value={draft.datePublished.slice(0, 10)}
          />
        </div>
        <CitationInput
          fillHeight
          onChange={(value) => onChange('citation', value)}
          surface="plain"
          value={draft.citation}
        />
      </div>
      {showDistribution ? <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h3 className="text-xl font-bold text-slate-950">Distribution metadata</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Provide the public download URL. Technical file details are generated after the source is processed.
          </p>
        </div>
        <div className="grid gap-4 p-5 md:grid-cols-2">
          <TextInput
            helpText="Direct public URL where this dataset content can be retrieved."
            label="Dataset download URL"
            maxLength={200}
            onChange={(value) => onChange('contentUrl', value)}
            placeholder="https://example.org/dataset/download"
            required
            surface="plain"
            value={draft.contentUrl}
          />
          <TextInput
            label="Encoding format"
            onChange={(value) => onChange('encodingFormat', value)}
            placeholder="Generated automatically"
            readOnly
            surface="plain"
            value={draft.encodingFormat}
          />
          <TextInput
            label="Filename"
            onChange={(value) => onChange('filename', value)}
            placeholder="Generated automatically"
            readOnly
            surface="plain"
            value={draft.filename}
          />
          <TextInput
            label="SHA-256"
            onChange={(value) => onChange('sha256', value)}
            placeholder="Generated automatically"
            readOnly
            surface="plain"
            value={draft.sha256}
          />
        </div>
      </div> : null}
    </div>
  )
}

function licenseOptionsForDataset(dataset: DatasetDraft, licenseOptions: SelectOption[]) {
  if (!dataset.license || licenseOptions.some((option) => option.value === dataset.license)) return licenseOptions
  return [{ label: dataset.licenseLabel || dataset.license, value: dataset.license }, ...licenseOptions]
}

function validSelectionIndex(datasetId: string, selectedDatasetId: string, index: number, length: number) {
  return selectedDatasetId === datasetId && index < length ? index : 0
}

function fieldsForDataset(dataset: DatasetDraft, selectedRecordSetIndex: number) {
  return dataset.mode === 'upload'
    ? dataset.recordSets[selectedRecordSetIndex]?.fields ?? []
    : [...dataset.fields, ...dataset.manualFields]
}

function recordSetOptionLabel(recordSet: DatasetDraft['recordSets'][number], index: number) {
  const name = recordSet.name || recordSet.id || `Record set ${index + 1}`
  return `${name} (${recordSet.fields.length} fields)`
}

function UploadedDistributionMetadata({
  dataset,
  onDistributionChange,
  onSelect,
  selectedDistributionIndex,
}: Readonly<{
  dataset: DatasetDraft
  onDistributionChange: DatasetDetailsEditorProps['onDistributionChange']
  onSelect: (index: number) => void
  selectedDistributionIndex: number
}>) {
  const selectedDistribution = dataset.distributions[selectedDistributionIndex]
  if (!selectedDistribution) {
    return <p className="p-5 text-sm text-slate-600">No distributions are declared in this Croissant file.</p>
  }
  const contentUrlHelp = selectedDistribution.containedInLabel
    ? 'Path used to find this file inside its containing archive or file set.'
    : 'Direct public URL where this dataset content can be retrieved.'

  return (
    <div className="grid gap-4 p-5">
      {dataset.distributions.length > 1 ? (
        <SelectInput
          label="Distribution"
          onChange={(value) => onSelect(Number(value))}
          options={dataset.distributions.map((distribution, index) => ({
            label: distribution.filename || distribution.id || `Distribution ${index + 1}`,
            value: String(index),
          }))}
          value={String(selectedDistributionIndex)}
        />
      ) : null}
      {selectedDistribution.containedInLabel ? (
        <p className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-slate-700">
          This file is contained in <strong>{selectedDistribution.containedInLabel}</strong>. Its content URL is a path inside that container, not a public download link.
        </p>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        <TextInput helpText={contentUrlHelp} label="Content URL" maxLength={500} onChange={(value) => onDistributionChange(selectedDistributionIndex, 'contentUrl', value)} value={selectedDistribution.contentUrl} />
        <TextInput label="Filename" maxLength={160} onChange={(value) => onDistributionChange(selectedDistributionIndex, 'filename', value)} value={selectedDistribution.filename} />
        <TextInput label="Encoding format" maxLength={120} onChange={(value) => onDistributionChange(selectedDistributionIndex, 'encodingFormat', value)} value={selectedDistribution.encodingFormat} />
        <TextInput helpText="Preferred checksum for stable, versioned dataset files. Enter the value exactly as published by the dataset provider." label="SHA-256" maxLength={200} onChange={(value) => onDistributionChange(selectedDistributionIndex, 'sha256', value)} value={selectedDistribution.sha256} />
        <TextInput helpText="Legacy checksum accepted by Croissant. Existing hexadecimal or encoded values are preserved as supplied." label="MD5" maxLength={200} onChange={(value) => onDistributionChange(selectedDistributionIndex, 'md5', value)} value={selectedDistribution.md5} />
      </div>
    </div>
  )
}

// For the user to view croissant fields, and add manual fields, in a way that bubbles/calls back up to the parent.
export function DatasetDetailsEditor({
  dataset,
  datasetManualField,
  licenseOptions,
  onAddManualField,
  onChange,
  onDistributionChange,
  onFieldChange,
  onManualFieldChange,
  onRemoveField,
  onRecordSetNameChange,
}: DatasetDetailsEditorProps) {
  const effectiveLicenseOptions = licenseOptionsForDataset(dataset, licenseOptions)
  const publicationFieldsRequired = dataset.mode === 'generate'
  const [distributionSelection, setDistributionSelection] = useState({ datasetId: '', index: 0 })
  const selectedDistributionIndex = validSelectionIndex(
    dataset.id, distributionSelection.datasetId, distributionSelection.index, dataset.distributions.length,
  )
  const [recordSetSelection, setRecordSetSelection] = useState({ datasetId: '', index: 0 })
  const selectedRecordSetIndex = validSelectionIndex(
    dataset.id, recordSetSelection.datasetId, recordSetSelection.index, dataset.recordSets.length,
  )
  const selectedRecordSet = dataset.recordSets[selectedRecordSetIndex]
  const fields = fieldsForDataset(dataset, selectedRecordSetIndex)
  const editedRecordSetIndex = dataset.mode === 'upload' ? selectedRecordSetIndex : undefined
  const recordSetName = selectedRecordSet?.name ?? ''
  const datasetName = dataset.name.trim() || 'Untitled dataset'
  const datasetNameLabel = datasetName.length > 16 ? `${datasetName.slice(0, 16)}...` : datasetName

  function changeRecordSetName(value: string) {
    if (dataset.mode === 'upload') onRecordSetNameChange(selectedRecordSetIndex, value)
    else onChange('recordSetName', value)
  }

  return (
    <div className="grid gap-6">
      <div className="rounded-xl border border-slate-200 bg-white" id={datasetMetadataSectionId}>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <span className="flex min-w-0 flex-wrap items-center gap-3">
            <h3 className="text-xl font-bold text-slate-950">Dataset metadata</h3>
            <span className="max-w-full truncate rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700" title={datasetName}>
              {datasetNameLabel}
            </span>
          </span>
          <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
            {dataset.mode === 'upload' ? 'from Croissant file' : 'generated'}
          </span>
        </div>
        <div className="grid gap-4 p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <TextInput
              helpText="Clear, human-readable title that helps people identify the dataset."
              label="Dataset name"
              maxLength={100}
              onChange={(value) => onChange('name', value)}
              required={publicationFieldsRequired}
              value={dataset.name}
            />
            <LicenseSelectInput
              licenseOptions={effectiveLicenseOptions}
              onChange={(value) => onChange('license', value)}
              required={publicationFieldsRequired}
              surface="plain"
              value={dataset.license}
            />
          </div>
          <TextArea
            label="Description"
            maxLength={publicationFieldsRequired ? 500 : undefined}
            onChange={(value) => onChange('description', value)}
            required={publicationFieldsRequired}
            value={dataset.description}
          />
          <div className="grid items-stretch gap-4 md:grid-cols-2">
            <div className="grid gap-4">
              <TextInput
                helpText="Public dataset landing or information page URL."
                label="Dataset landing page"
                maxLength={200}
                onChange={(value) => onChange('url', value)}
                value={dataset.url}
              />
              <TextInput
                helpText="Version identifier for this dataset release. Semantic versions such as 1.0.0 are recommended, but other versioning schemes are accepted."
                label="Dataset version"
                maxLength={50}
                onChange={(value) => onChange('datasetVersion', value)}
                placeholder="0.0.1"
                required={publicationFieldsRequired}
                value={dataset.datasetVersion}
              />
              <TextInput
                inputType="date"
                label="Date published"
                maxLength={20}
                onChange={(value) => onChange('datePublished', value)}
                required={publicationFieldsRequired}
                value={dataset.datePublished.slice(0, 10)}
              />
            </div>
            <CitationInput
              fillHeight
              onChange={(value) => onChange('citation', value)}
              value={dataset.citation}
            />
          </div>
        </div>
      </div>

      {dataset.mode === 'upload' ? (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-5 py-4">
            <h3 className="text-xl font-bold text-slate-950">Distribution metadata</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Select and edit one file description at a time. Unchanged Croissant properties are preserved.
            </p>
          </div>
          <UploadedDistributionMetadata
            dataset={dataset}
            onDistributionChange={onDistributionChange}
            onSelect={(index) => setDistributionSelection({ datasetId: dataset.id, index })}
            selectedDistributionIndex={selectedDistributionIndex}
          />
        </div>
      ) : (
      <fieldset className="grid gap-6">
      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h3 className="text-xl font-bold text-slate-950">Distribution metadata</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            These values describe the selected source file and will be included in the generated Croissant metadata.
          </p>
        </div>
        <div className="grid gap-4 p-5 md:grid-cols-2">
          <TextInput
            helpText="Direct public URL where this dataset content can be retrieved."
            label="Dataset download URL"
            maxLength={200}
            onChange={(value) => onChange('contentUrl', value)}
            required
            value={dataset.contentUrl}
          />
          <TextInput
            label="Encoding format"
            maxLength={80}
            onChange={(value) => onChange('encodingFormat', value)}
            placeholder="text/csv"
            readOnly
            value={dataset.encodingFormat}
          />
          <TextInput
            label="Filename"
            maxLength={160}
            onChange={(value) => onChange('filename', value)}
            readOnly
            value={dataset.filename}
          />
          <TextInput
            label="SHA-256"
            maxLength={80}
            onChange={(value) => onChange('sha256', value)}
            readOnly
            value={dataset.sha256}
          />
        </div>
      </div>
      </fieldset>
      )}

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h3 className="text-xl font-bold text-slate-950">Field entries</h3>
        </div>
        <div className="grid gap-5 p-5">
          {dataset.mode === 'upload' && dataset.recordSets.length > 1 ? (
            <SelectInput
              label="Record set"
              onChange={(value) => setRecordSetSelection({ datasetId: dataset.id, index: Number(value) })}
              options={dataset.recordSets.map((recordSet, index) => ({
                label: recordSetOptionLabel(recordSet, index),
                value: String(index),
              }))}
              value={String(selectedRecordSetIndex)}
            />
          ) : null}
          {dataset.mode === 'upload' && selectedRecordSet ? (
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-600">
              <span><strong>{selectedRecordSet.fields.length}</strong> fields</span>
              {selectedRecordSet.sourceFileLabel ? (
                <span>Source: <strong>{selectedRecordSet.sourceFileLabel}</strong></span>
              ) : null}
            </div>
          ) : null}
          <TextInput
            label="Record set name"
            maxLength={120}
            onChange={changeRecordSetName}
            required
            value={dataset.mode === 'upload' ? recordSetName : dataset.recordSetName}
          />

          {fields.length ? (
            <div className="min-w-0 overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full min-w-[760px] divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Actions</th>
                    <th className="px-4 py-3">Field name</th>
                    <th className="px-4 py-3">Suggested datatype</th>
                    <th className="px-4 py-3">Description</th>
                    <th className="px-4 py-3">Example</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {fields.map((field) => (
                    <tr key={field.id}>
                      <td className="px-4 py-3">
                        <button
                          aria-label={`Remove ${field.name}`}
                          className="inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border border-red-200 text-red-600 hover:bg-red-50 hover:shadow-sm"
                          onClick={() => onRemoveField(editedRecordSetIndex, field.id)}
                          title={`Remove ${field.name}`}
                          type="button"
                        >
                          <TrashIcon className="h-4 w-4" aria-hidden="true" />
                        </button>
                      </td>
                      <td className="w-52 px-4 py-3">
                        <input
                          aria-label={`Column name for ${field.name || 'unnamed field'}`}
                          className="h-10 w-full min-w-0 rounded-lg border border-slate-200 bg-white px-3 font-mono text-xs text-slate-950 outline-none focus:border-blue-500"
                          maxLength={120}
                          onChange={(event) => onFieldChange(editedRecordSetIndex, field.id, 'name', event.target.value)}
                          value={field.name}
                        />
                      </td>
                      <td className="w-44 px-4 py-3">
                        <select
                          className="h-10 w-full min-w-0 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none focus:border-blue-500"
                          onChange={(event) => onFieldChange(editedRecordSetIndex, field.id, 'dataType', event.target.value)}
                          value={field.dataType}
                        >
                          {fieldDataTypeOptions.map((option) => (
                            <option disabled={option.disabled} key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <input
                          className="h-10 w-full min-w-0 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none focus:border-blue-500"
                          maxLength={240}
                          onChange={(event) => onFieldChange(editedRecordSetIndex, field.id, 'description', event.target.value)}
                          value={field.description}
                        />
                      </td>
                      <td className="max-w-40 px-4 py-3 text-xs text-slate-700" title={field.example}>
                        <span className="block truncate">{field.example}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              No fields detected yet
            </p>
          )}

          {dataset.mode === 'generate' ? (
          <div className="grid gap-4 rounded-xl border border-slate-200 bg-slate-50 p-5">
            <h4 className="text-base font-bold text-slate-950">Manual fields</h4>
            <div className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(10rem,1fr)]">
              <TextInput
                label="Field name"
                maxLength={120}
                onChange={(value) => onManualFieldChange('name', value)}
                surface="plain"
                value={datasetManualField.name}
              />
              <SelectInput
                label="Data type"
                onChange={(value) => onManualFieldChange('dataType', value)}
                options={fieldDataTypeOptions}
                surface="plain"
                value={datasetManualField.dataType}
              />
            </div>
            <TextInput
              label="Description"
              maxLength={240}
              onChange={(value) => onManualFieldChange('description', value)}
              surface="plain"
              value={datasetManualField.description}
            />
            <TextInput
              label="Example"
              maxLength={200}
              onChange={(value) => onManualFieldChange('example', value)}
              surface="plain"
              value={datasetManualField.example}
            />
            <button
              className="inline-flex h-11 w-fit cursor-pointer items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 text-sm font-semibold text-white hover:bg-blue-700"
              onClick={() => onAddManualField(editedRecordSetIndex)}
              type="button"
            >
              <PlusIcon className="h-4 w-4" aria-hidden="true" />
              Add manual field
            </button>
          </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
