import { useState, type ReactNode } from 'react'
import { ArrowPathIcon, CheckCircleIcon, ChevronDownIcon, ExclamationTriangleIcon, XCircleIcon } from '@heroicons/react/24/outline'
import { getValidationSchemaApiV1SchemasVersionGet, type ValidationCheckResponse, type ValidationDetailResponse } from '../api/client'
import { registrationValidationDetails } from '../api/validationDiagnostics'
import { formatValidatorMessage } from './validationMessage'

function ValidatorMessage({ message }: Readonly<{ message: string }>) {
  const formatted = formatValidatorMessage(message)
  if (!formatted) return <p className="whitespace-pre-wrap leading-6">{message}</p>

  return <fieldset aria-label={message} className="m-0 min-w-0 border-0 p-0">
    <div aria-hidden="true">
      <p className="leading-6">{formatted.prefix}</p>
      <ul className="mt-2 grid gap-1.5 pl-5">
        {formatted.alternatives.map((value, index) => <li className="list-disc" key={value}>
          <code className="break-all font-mono text-[0.8125rem] text-red-800">{value}</code>
          {index === formatted.alternatives.length - 1 && formatted.suffix ? <span>{formatted.suffix}</span> : null}
        </li>)}
      </ul>
    </div>
  </fieldset>
}

function sourceHref(detail: ValidationDetailResponse) {
  if (!detail.source_url) return undefined
  const lineFragment = detail.line ? `#L${detail.line}` : ''
  return `${detail.source_url}${lineFragment}`
}

function sourcePosition(detail: ValidationDetailResponse) {
  if (detail.location_kind === 'containing_object') {
    if (!detail.line) return 'The missing field has no existing line.'
    const column = detail.column ? `, column ${detail.column}` : ''
    return `Containing object starts at line ${detail.line}${column}. The missing field has no existing line.`
  }
  if (!detail.line) return null
  const column = detail.column ? `, column ${detail.column}` : ''
  return `Line ${detail.line}${column}.`
}

function DiagnosticLocation({ detail }: Readonly<{ detail: ValidationDetailResponse }>) {
  const position = sourcePosition(detail)
  const href = sourceHref(detail)
  const hasLocation = detail.json_path || detail.requirement || detail.expected_format
    || detail.location_description || detail.source_file || position
  if (!hasLocation) return null

  return <dl className="mt-3 grid gap-2 text-slate-700">
    {detail.location_description ? <div className="grid gap-1 sm:grid-cols-[9rem_1fr]"><dt className="font-semibold">Where to fix</dt><dd>{detail.location_description}</dd></div> : null}
    {detail.source_file ? <div className="grid gap-1 sm:grid-cols-[9rem_1fr]"><dt className="font-semibold">File</dt><dd>{href ? <a className="text-blue-700 underline" href={href} target="_blank" rel="noreferrer">{detail.source_file}</a> : detail.source_file}</dd></div> : null}
    {position ? <div className="grid gap-1 sm:grid-cols-[9rem_1fr]"><dt className="font-semibold">Source position</dt><dd>{position}</dd></div> : null}
    {detail.json_path ? <div className="grid gap-1 sm:grid-cols-[9rem_1fr]"><dt className="font-semibold">JSON path</dt><dd className="font-mono">{detail.json_path}</dd></div> : null}
    {detail.requirement ? <div className="grid gap-1 sm:grid-cols-[9rem_1fr]"><dt className="font-semibold">Requirement</dt><dd>{detail.requirement}</dd></div> : null}
    {detail.expected_format ? <div className="grid gap-1 sm:grid-cols-[9rem_1fr]"><dt className="font-semibold">Expected format</dt><dd className="whitespace-pre-wrap">{detail.expected_format}</dd></div> : null}
  </dl>
}

export function DiagnosticErrors({ details, unavailableLocation = false }: Readonly<{ details: ValidationDetailResponse[]; unavailableLocation?: boolean }>) {
  if (!details.length) return null
  return <ul className="grid gap-3">
    {details.map((detail, index) => (
      <li className="break-words rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-red-700" key={`${detail.message}-${index}`}>
        <ValidatorMessage message={detail.message} />
        <DiagnosticLocation detail={detail} />
      </li>
    ))}
    {unavailableLocation && details.some(detail => !detail.json_path && !detail.location_description && !detail.source_file && !detail.line) ? <li className="text-xs text-slate-600">The validator did not supply a source location for some errors.</li> : null}
  </ul>
}

function SchemaViewer({ version, dialect }: Readonly<{ version: string; dialect?: string | null }>) {
  const [schema, setSchema] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  async function load() {
    if (loading || schema) return
    setLoading(true)
    setError(false)
    try {
      const response = await getValidationSchemaApiV1SchemasVersionGet({ path: { version }, throwOnError: true })
      setSchema(JSON.stringify(response.data, null, 2))
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  return <details className="mt-2" onToggle={event => { if (event.currentTarget.open) void load() }}>
    <summary className="cursor-pointer text-blue-700 underline">View schema</summary>
    {dialect ? <p className="mt-2 break-all text-xs text-slate-600">JSON Schema dialect: {dialect.includes('draft-07') ? 'Draft 7' : dialect}</p> : null}
    {loading ? <p className="mt-2">Loading schema…</p> : null}
    {error ? <p className="mt-2 text-slate-700">Could not load the schema. <button className="cursor-pointer text-blue-700 underline" onClick={() => void load()} type="button">Retry schema loading</button></p> : null}
    {schema ? <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap break-all rounded bg-slate-50 p-3 text-xs text-slate-700">{schema}</pre> : null}
  </details>
}

const labels = { PENDING: 'Pending', RUNNING: 'Running', PASSED: 'Passed', FAILED: 'Failed', NOT_RUN: 'Not run' }

function statusPresentation(status: ValidationCheckResponse['status']): { icon: ReactNode; tone: string } {
  if (status === 'PASSED') return {
    icon: <CheckCircleIcon className="h-4 w-4 flex-none" aria-hidden="true" />,
    tone: 'text-emerald-700',
  }
  if (status === 'FAILED') return {
    icon: <XCircleIcon className="h-4 w-4 flex-none" aria-hidden="true" />,
    tone: 'text-red-700',
  }
  if (status === 'RUNNING') return {
    icon: <ArrowPathIcon className="h-4 w-4 flex-none animate-spin" aria-hidden="true" />,
    tone: 'text-blue-700',
  }
  return {
    icon: <span className="h-2 w-2 flex-none rounded-full bg-current" aria-hidden="true" />,
    tone: 'text-slate-500',
  }
}

function CheckStatus({ status, interrupted, warnings = 0 }: Readonly<{ status: ValidationCheckResponse['status']; interrupted: boolean; warnings?: number }>) {
  if (interrupted && ['PENDING', 'RUNNING'].includes(status)) return <span className="text-slate-600">Unconfirmed</span>
  if (status === 'PASSED' && warnings > 0) return <span className="inline-flex items-center gap-2 text-sm font-medium text-amber-700"><ExclamationTriangleIcon className="h-4 w-4 flex-none" aria-hidden="true" />Passed with warnings</span>
  const { icon, tone } = statusPresentation(status)
  return <span className={`inline-flex items-center gap-2 text-sm font-medium ${tone}`}>{icon}{labels[status]}</span>
}

function CheckProvenance({ check }: Readonly<{ check: ValidationCheckResponse }>) {
  if (check.profile_version) return <>
    <span>{check.schema_title ?? `BioCypher Adapter Schema ${check.profile_version}`}</span>
    <SchemaViewer key={check.profile_version} version={check.profile_version} dialect={check.schema_dialect} />
  </>
  if (check.validator_name) return <span><span>{check.validator_name}</span>{' '}<span className="inline-block">{check.validator_version}</span>{' '}<span className="text-slate-500">(validator)</span></span>
  if (check.id === 'datasets') return <span className="text-slate-500">Per dataset</span>
  if (check.id === 'semantics' && ['RUNNING', 'PASSED', 'FAILED'].includes(check.status)) return <span>Registry rules</span>
  return <span className="text-slate-500">{check.id === 'file' ? 'No schema' : 'Not applied'}</span>
}

function CheckDetails({
  check,
  details,
  detailsId,
  expanded,
}: Readonly<{
  check: ValidationCheckResponse
  details: ValidationDetailResponse[]
  detailsId: string
  expanded: boolean
}>) {
  return <div className="pb-4" hidden={!expanded} id={detailsId}>
    {check.description ? <p className="mb-3 max-w-[80ch] text-sm leading-6 text-slate-600">{check.description}</p> : null}
    {check.reason ? <p className="mb-3 max-w-[80ch] text-sm leading-6 text-slate-600">{check.reason}</p> : null}
    {check.warnings?.length ? <div className={details.length ? 'mb-4' : ''}>
      <h5 className="mb-2 text-sm font-semibold text-amber-800">Validation warnings ({check.warnings.length})</h5>
      <ul className="grid gap-3">
        {check.warnings.map((warning, index) => <li className="whitespace-pre-wrap break-words rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 leading-6 text-amber-900" key={`${warning}-${index}`}>{warning}</li>)}
      </ul>
    </div> : null}
    {details.length ? <div><h5 className="mb-2 text-sm font-semibold text-slate-700">Validation errors ({details.length})</h5><DiagnosticErrors details={details} unavailableLocation /></div> : null}
  </div>
}

function ValidationCheck({
  check,
  expanded,
  expandable,
  interrupted,
  nested = false,
  onToggle,
}: Readonly<{
  check: ValidationCheckResponse
  expanded: boolean
  expandable: boolean
  interrupted: boolean
  nested?: boolean
  onToggle: () => void
}>) {
  const details = registrationValidationDetails({ validation_errors: check.errors, validation_details: check.validation_details })
  const detailsId = `${check.id.replace(/[^a-zA-Z0-9_-]/g, '-')}-details`
  const toggleLabel = expanded ? 'Collapse' : 'Expand'
  return <div className={nested ? 'pl-4' : ''} data-check-id={check.id}>
    <div className="flex gap-3 py-4">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            {check.dataset_index !== undefined && check.dataset_index !== null ? <span className="mb-1 block text-sm text-slate-500">Dataset {check.dataset_index + 1}</span> : null}
            <h4 className="break-words text-sm font-semibold text-slate-900">{check.name}</h4>
          </div>
          <CheckStatus status={check.status} interrupted={interrupted} warnings={check.warnings?.length} />
        </div>
        <div className="mt-1 text-sm leading-5 text-slate-600"><CheckProvenance check={check} /></div>
      </div>
      {expandable ? <button
        aria-controls={detailsId}
        aria-expanded={expanded}
        aria-label={`${toggleLabel} details for ${check.name}`}
        className="flex h-10 w-10 flex-none cursor-pointer items-center justify-center rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        onClick={onToggle}
        type="button"
      ><ChevronDownIcon aria-hidden="true" className={`h-5 w-5 transition-transform ${expanded ? 'rotate-180' : ''}`} /></button> : null}
    </div>
    {expandable ? <CheckDetails check={check} details={details} detailsId={detailsId} expanded={expanded} /> : null}
  </div>
}

export function RegistrationValidationChecks({ checks, description = 'Adapter checks are followed by an independent check for each embedded dataset.', interrupted = false }: Readonly<{ checks: ValidationCheckResponse[]; description?: string; interrupted?: boolean }>) {
  const expandableIds = new Set(checks.filter(check => check.reason || check.description || check.errors?.length || check.warnings?.length || check.validation_details?.length || check.profile_version).map(check => check.id))
  const failedIds = new Set(checks.filter(check => check.status === 'FAILED' && check.id !== 'datasets').map(check => check.id))
  const warningIds = new Set(checks.filter(check => check.warnings?.length && check.id !== 'datasets').map(check => check.id))
  const [expansionOverrides, setExpansionOverrides] = useState<Record<string, boolean>>({})
  const topLevelChecks = checks.filter(check => !check.parent_id && check.id !== 'datasets')
  const datasetGroup = checks.find(check => check.id === 'datasets')
  const datasetChecks = checks.filter(check => check.parent_id === 'datasets')
  const isExpanded = (id: string) => expansionOverrides[id] ?? (failedIds.has(id) || warningIds.has(id))
  const allExpanded = expandableIds.size > 0 && Array.from(expandableIds).every(isExpanded)

  function toggleCheck(id: string) {
    setExpansionOverrides(current => ({ ...current, [id]: !(current[id] ?? (failedIds.has(id) || warningIds.has(id))) }))
  }

  return <div className="mt-6 text-sm">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 className="text-lg font-semibold text-slate-950">Validation report</h3>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{description}</p>
      </div>
      {expandableIds.size ? <div className="flex justify-end">
      <button
        className="min-h-11 cursor-pointer rounded-lg px-3 text-sm font-semibold text-blue-700 hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        onClick={() => setExpansionOverrides(Object.fromEntries(Array.from(expandableIds, id => [id, !allExpanded])))}
        type="button"
      >{allExpanded ? 'Collapse details' : 'Expand details'}</button>
      </div> : null}
    </div>
    <div className="mt-4 divide-y divide-slate-100 border-y border-slate-200">
      {topLevelChecks.map(check => <ValidationCheck
        check={check}
        expanded={isExpanded(check.id)}
        expandable={expandableIds.has(check.id)}
        interrupted={interrupted}
        key={check.id}
        onToggle={() => toggleCheck(check.id)}
      />)}
      {datasetGroup ? <section className="py-4" aria-labelledby="embedded-datasets-heading">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h4 className="text-sm font-semibold text-slate-900" id="embedded-datasets-heading">Embedded datasets</h4>
            <p className="mt-1 text-sm text-slate-600">{datasetChecks.length} {datasetChecks.length === 1 ? 'dataset' : 'datasets'} checked independently</p>
          </div>
          <CheckStatus status={datasetGroup.status} interrupted={interrupted} warnings={datasetGroup.warnings?.length} />
        </div>
        <div className="mt-3 divide-y divide-slate-100 border-l-2 border-slate-200 pl-2">
          {datasetChecks.map(check => <ValidationCheck
            check={check}
            expanded={isExpanded(check.id)}
            expandable={expandableIds.has(check.id)}
            interrupted={interrupted}
            key={check.id}
            nested
            onToggle={() => toggleCheck(check.id)}
          />)}
        </div>
      </section> : null}
    </div>
  </div>
}
