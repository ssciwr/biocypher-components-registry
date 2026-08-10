import { PlusIcon } from '@heroicons/react/24/outline'
import type {
  CreatorDraft,
  CreatorType,
  DatasetDraft,
  DatasetMode,
  LicenseOption,
  SelectOption,
} from './types'
import { normaliseOrcid } from './utils'

type TextInputProps = Readonly<{
  label: string
  maxLength?: number
  onChange: (value: string) => void
  placeholder?: string
  required?: boolean
  value: string
}>

type TextAreaProps = Readonly<TextInputProps>

type SelectInputProps<TValue extends string> = Readonly<{
  label: string
  onChange: (value: TValue) => void
  options: ReadonlyArray<SelectOption<TValue>>
  required?: boolean
  surface?: 'muted' | 'plain'
  value: TValue
}>

type CreatorEditorProps = Readonly<{
  draft: CreatorDraft
  onAdd: () => void
  onChange: (field: keyof CreatorDraft, value: string) => void
}>

type DatasetEditorProps = Readonly<{
  draft: DatasetDraft
  licenseOptions: LicenseOption[]
  onAdd: () => void
  onChange: (field: keyof DatasetDraft, value: string) => void
}>

const creatorTypeOptions: ReadonlyArray<SelectOption<CreatorType>> = [
  { label: 'Person', value: 'Person' },
  { label: 'Organization', value: 'Organization' },
]

const datasetModeOptions: ReadonlyArray<SelectOption<DatasetMode>> = [
  { label: 'Croissant file path', value: 'croissant' },
  { label: 'Manual dataset information', value: 'manual' },
]

/*
 * AI-Generated.
 */
export function TextInput({
  label,
  maxLength,
  onChange,
  placeholder,
  required = false,
  value,
}: TextInputProps) {
  return (
    <label className="grid gap-2 text-sm font-semibold text-slate-950">
      <span>{label}</span>
      <input
        className="h-12 rounded-xl border border-slate-200 bg-slate-50 px-4 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        type="text"
        value={value}
      />
    </label>
  )
}

/*
 * AI-Generated.
 */
export function TextArea({
  label,
  maxLength,
  onChange,
  placeholder,
  required = false,
  value,
}: TextAreaProps) {
  return (
    <label className="grid gap-2 text-sm font-semibold text-slate-950">
      <span>{label}</span>
      <textarea
        className="min-h-28 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        value={value}
      />
    </label>
  )
}

/*
 * AI-Generated.
 */
export function SelectInput<TValue extends string>({
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
    <label className="grid gap-2 text-sm font-semibold text-slate-950">
      <span>{label}</span>
      <select
        className={`h-12 rounded-xl border border-slate-200 px-4 text-base font-normal text-slate-950 outline-none focus:border-blue-500 ${backgroundClass}`}
        onChange={(event) => onChange(event.target.value as TValue)}
        required={required}
        value={value}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
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
export function CreatorEditor({ draft, onAdd, onChange }: CreatorEditorProps) {
  return (
    <div className="grid gap-4 rounded-xl border border-slate-200 bg-slate-50 p-5">
      <TextInput
        label="Name *"
        maxLength={100}
        onChange={(value) => onChange('name', value)}
        placeholder="Example: Robert Koch"
        value={draft.name}
      />
      <SelectInput
        label="Creator type"
        onChange={(value) => onChange('creatorType', value)}
        options={creatorTypeOptions}
        surface="plain"
        value={draft.creatorType}
      />
      <TextInput
        label="Affiliation(s) (comma-separated)"
        maxLength={100}
        onChange={(value) => onChange('affiliation', value)}
        placeholder="Example: Robert Koch Institute, University of Goettingen"
        value={draft.affiliation}
      />
      <TextInput
        label="ORCID ID"
        onChange={(value) => onChange('orcid', normaliseOrcid(value))}
        placeholder="Example: https://orcid.org/1234-5678-9101-1121"
        value={draft.orcid}
      />
      <TextInput
        label="Email"
        maxLength={100}
        onChange={(value) => onChange('email', value)}
        placeholder="Example: robert.koch@rki.de-mail.de"
        value={draft.email}
      />
      <TextInput
        label="URL"
        maxLength={200}
        onChange={(value) => onChange('url', value)}
        placeholder="Example: www.rki.de"
        value={draft.url}
      />
      <button
        className="inline-flex h-11 w-fit cursor-pointer items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 text-sm font-semibold text-white hover:bg-blue-700"
        onClick={onAdd}
        type="button"
      >
        <PlusIcon className="h-4 w-4" aria-hidden="true" />
        Add creator
      </button>
    </div>
  )
}

/*
 * AI-Generated.
 */
export function DatasetEditor({ draft, licenseOptions, onAdd, onChange }: DatasetEditorProps) {
  const isCroissantDataset = draft.mode === 'croissant'

  return (
    <div className="grid gap-4 rounded-xl border border-slate-200 bg-slate-50 p-5">
      <SelectInput
        label="Dataset source"
        onChange={(value) => onChange('mode', value)}
        options={datasetModeOptions}
        surface="plain"
        value={draft.mode}
      />

      {isCroissantDataset ? (
        <TextInput
          label="Croissant file path"
          onChange={(value) => onChange('path', value)}
          placeholder="/srv/biocypher/examples/dataset/croissant.jsonld"
          value={draft.path}
        />
      ) : (
        <>
          <TextInput
            label="Input path"
            onChange={(value) => onChange('input', value)}
            placeholder="/srv/biocypher/examples/dataset-demo"
            value={draft.input}
          />
          <TextInput
            label="Dataset name"
            maxLength={100}
            onChange={(value) => onChange('name', value)}
            placeholder="Example Dataset"
            value={draft.name}
          />
          <TextArea
            label="Description"
            maxLength={500}
            onChange={(value) => onChange('description', value)}
            placeholder="Small people dataset."
            value={draft.description}
          />
          <SelectInput
            label="License"
            onChange={(value) => onChange('license', value)}
            options={licenseOptions}
            surface="plain"
            value={draft.license}
          />
          <TextInput
            label="URL"
            maxLength={200}
            onChange={(value) => onChange('url', value)}
            placeholder="https://example.org/people"
            value={draft.url}
          />
          <TextInput
            label="Citation"
            maxLength={200}
            onChange={(value) => onChange('citation', value)}
            placeholder="https://example.org/people"
            value={draft.citation}
          />
          <TextInput
            label="Dataset version"
            maxLength={50}
            onChange={(value) => onChange('datasetVersion', value)}
            placeholder="1.0.0"
            value={draft.datasetVersion}
          />
          <TextInput
            label="Date published"
            maxLength={20}
            onChange={(value) => onChange('datePublished', value)}
            placeholder="2026-04-17"
            value={draft.datePublished}
          />
        </>
      )}

      <button
        className="inline-flex h-11 w-fit cursor-pointer items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 text-sm font-semibold text-white hover:bg-blue-700"
        onClick={onAdd}
        type="button"
      >
        <PlusIcon className="h-4 w-4" aria-hidden="true" />
        Add dataset
      </button>
    </div>
  )
}
