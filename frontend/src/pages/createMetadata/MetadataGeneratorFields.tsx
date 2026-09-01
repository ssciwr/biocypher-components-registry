import { DocumentArrowUpIcon, DocumentCheckIcon, PlusIcon, TrashIcon } from '@heroicons/react/24/outline'
import type {
  CreatorDraft,
  CreatorType,
  DatasetDatasetManualField,
  DatasetDraft,
  SelectOption,
} from './types'
import { normaliseOrcid } from './utils'

type TextInputProps = Readonly<{
  inputType?: 'date' | 'text'
  label: string
  maxLength?: number
  name?: string
  onChange: (value: string) => void
  placeholder?: string
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
  onSourceFileChange: (file: File | null) => void
  sourceRequired?: boolean
}>

type DatasetDetailsEditorProps = Readonly<{
  dataset: DatasetDraft
  datasetManualField: DatasetDatasetManualField
  licenseOptions: SelectOption[]
  onAddManualField: () => void
  onChange: (field: keyof DatasetDraft, value: string) => void
  onFieldChange: (fieldId: string, field: keyof DatasetDatasetManualField, value: string) => void
  onManualFieldChange: (field: keyof DatasetDatasetManualField, value: string) => void
  onRemoveField: (fieldId: string) => void
}>

type LicenseSelectInputProps = Readonly<{
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


/** todo note:
 *  Should review whether we should actually use a UI library like shadcn because the custom coding is extra code
 *  and is beginning not to make sense.
 */

export function TextInput({
  inputType = 'text',
  label,
  maxLength,
  name,
  onChange,
  placeholder,
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
      <span>{label}{required ? ' *' : ''}</span>
      <input
        className={`h-12 w-full min-w-0 rounded-xl border border-slate-200 px-4 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 ${backgroundClass}`}
        maxLength={maxLength}
        name={name}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        type={inputType}
        value={value}
      />
    </label>
  )
}

export function TextArea({
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
    <label className="grid min-w-0 gap-2 text-sm font-semibold text-slate-950">
      <span>{label}{required ? ' *' : ''}</span>
      <textarea
        className={`min-h-28 w-full min-w-0 rounded-xl border border-slate-200 px-4 py-3 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 ${backgroundClass}`}
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        value={value}
      />
    </label>
  )
}

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
    <label className="grid min-w-0 gap-2 text-sm font-semibold text-slate-950">
      <span>{label}{required ? ' *' : ''}</span>
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
  label = 'License',
  licenseOptions,
  onChange,
  required = false,
  surface = 'muted',
  value,
}: LicenseSelectInputProps) {
  return (
    <SelectInput
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
  sourceRequired = false,
}: DatasetGenerateEditorProps) {
  return (
    <div className="grid gap-4 rounded-xl border border-slate-200 bg-slate-50 p-5">
      <FileInput
        accept=".csv,.tsv,.txt,.json,.jsonl,.gz,text/csv,text/tab-separated-values,application/json,application/gzip"
        label="Source dataset file"
        onChange={onSourceFileChange}
        required={sourceRequired}
      />
      {draft.sourceFileName ? (
        <p className="inline-flex w-fit items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-700">
          <DocumentArrowUpIcon className="h-4 w-4" aria-hidden="true" />
          {draft.sourceFileName}
        </p>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        <TextInput
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
        maxLength={500}
        onChange={(value) => onChange('description', value)}
        placeholder="Small people dataset."
        surface="plain"
        value={draft.description}
      />
      <div className="grid gap-4 md:grid-cols-2">
        <TextInput
          label="URL"
          maxLength={200}
          onChange={(value) => onChange('url', value)}
          placeholder="https://example.org/people"
          surface="plain"
          value={draft.url}
        />
        <TextInput
          label="Citation"
          maxLength={200}
          onChange={(value) => onChange('citation', value)}
          placeholder="https://example.org/people"
          surface="plain"
          value={draft.citation}
        />
        <TextInput
          label="Dataset version"
          maxLength={50}
          onChange={(value) => onChange('datasetVersion', value)}
          placeholder="0.0.1"
          required
          surface="plain"
          value={draft.datasetVersion}
        />
        <TextInput
          inputType="date"
          label="Date published"
          maxLength={20}
          onChange={(value) => onChange('datePublished', value)}
          placeholder="2026-04-17"
          required
          surface="plain"
          value={draft.datePublished.slice(0, 10)}
        />
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
  onFieldChange,
  onManualFieldChange,
  onRemoveField,
}: DatasetDetailsEditorProps) {
  const fields = [...dataset.fields, ...dataset.manualFields]
  const datasetName = dataset.name.trim() || 'Untitled dataset'
  const datasetNameLabel = datasetName.length > 16 ? `${datasetName.slice(0, 16)}...` : datasetName

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
              label="Dataset name"
              maxLength={100}
              onChange={(value) => onChange('name', value)}
              required
              value={dataset.name}
            />
            <LicenseSelectInput
              licenseOptions={licenseOptions}
              onChange={(value) => onChange('license', value)}
              required
              surface="plain"
              value={dataset.license}
            />
            <TextInput
              label="Dataset version"
              maxLength={50}
              onChange={(value) => onChange('datasetVersion', value)}
              placeholder="0.0.1"
              required
              value={dataset.datasetVersion}
            />
            <TextInput
              inputType="date"
              label="Date published"
              maxLength={20}
              onChange={(value) => onChange('datePublished', value)}
              required
              value={dataset.datePublished.slice(0, 10)}
            />
          </div>
          <TextArea
            label="Description"
            maxLength={500}
            onChange={(value) => onChange('description', value)}
            required
            value={dataset.description}
          />
          <div className="grid gap-4 md:grid-cols-2">
            <TextInput
              label="URL"
              maxLength={200}
              onChange={(value) => onChange('url', value)}
              value={dataset.url}
            />
            <TextInput
              label="Citation"
              maxLength={200}
              onChange={(value) => onChange('citation', value)}
              value={dataset.citation}
            />
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h3 className="text-xl font-bold text-slate-950">Distribution metadata</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            These values describe the selected source file and will be included in the generated Croissant metadata.
          </p>
        </div>
        <div className="grid gap-4 p-5 md:grid-cols-2">
          <TextInput
            label="Content URL"
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
            value={dataset.encodingFormat}
          />
          <TextInput
            label="Filename"
            maxLength={160}
            onChange={(value) => onChange('filename', value)}
            value={dataset.filename}
          />
          <TextInput
            label="SHA-256"
            maxLength={80}
            onChange={(value) => onChange('sha256', value)}
            value={dataset.sha256}
          />
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h3 className="text-xl font-bold text-slate-950">Field entries</h3>
        </div>
        <div className="grid gap-5 p-5">
          <TextInput
            label="Record set name"
            maxLength={120}
            onChange={(value) => onChange('recordSetName', value)}
            required
            value={dataset.recordSetName}
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
                          onClick={() => onRemoveField(field.id)}
                          title={`Remove ${field.name}`}
                          type="button"
                        >
                          <TrashIcon className="h-4 w-4" aria-hidden="true" />
                        </button>
                      </td>
                      <td className="max-w-48 px-4 py-3 font-mono text-xs text-slate-950" title={field.name}>
                        <span className="block truncate">{field.name}</span>
                      </td>
                      <td className="w-44 px-4 py-3">
                        <select
                          className="h-10 w-full min-w-0 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none focus:border-blue-500"
                          onChange={(event) => onFieldChange(field.id, 'dataType', event.target.value)}
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
                          onChange={(event) => onFieldChange(field.id, 'description', event.target.value)}
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
              onClick={onAddManualField}
              type="button"
            >
              <PlusIcon className="h-4 w-4" aria-hidden="true" />
              Add manual field
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
