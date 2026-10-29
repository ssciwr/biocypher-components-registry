import { useId, useState } from 'react'
import { ArrowPathIcon, CheckCircleIcon, ChevronDownIcon, XCircleIcon } from '@heroicons/react/24/outline'
import { getValidationSchemaApiV1SchemasVersionGet, type ValidationCheckResponse, type ValidationDetailResponse } from '../api/client'
import { registrationValidationDetails } from '../api/validationDiagnostics'

export function DiagnosticErrors({ details, unavailableLocation = false }: Readonly<{ details: ValidationDetailResponse[]; unavailableLocation?: boolean }>) {
  if (!details.length) return null
  return <ul className="grid gap-3">
    {details.map((detail, index) => (
      <li className="break-words rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-red-700" key={`${detail.message}-${index}`}>
        <p className="whitespace-pre-wrap">{detail.message}</p>
        {detail.json_path || detail.requirement || detail.expected_format || detail.location_description || detail.source_file || detail.line ? (
          <dl className="mt-3 grid gap-2 text-slate-700">
            {detail.location_description ? <div className="grid gap-1 sm:grid-cols-[9rem_1fr]"><dt className="font-semibold">Where to fix</dt><dd>{detail.location_description}</dd></div> : null}
            {detail.source_file ? <div className="grid gap-1 sm:grid-cols-[9rem_1fr]"><dt className="font-semibold">File</dt><dd>{detail.source_url ? <a className="text-blue-700 underline" href={`${detail.source_url}${detail.line ? `#L${detail.line}` : ''}`} target="_blank" rel="noreferrer">{detail.source_file}</a> : detail.source_file}</dd></div> : null}
            {detail.line || detail.location_kind === 'containing_object' ? <div className="grid gap-1 sm:grid-cols-[9rem_1fr]">
              <dt className="font-semibold">Source position</dt>
              <dd>{detail.location_kind === 'containing_object'
                ? <>{detail.line ? `Containing object starts at line ${detail.line}${detail.column ? `, column ${detail.column}` : ''}. ` : ''}The missing field has no existing line.</>
                : <>Line {detail.line}{detail.column ? `, column ${detail.column}` : ''}.</>}
              </dd>
            </div> : null}
            {detail.json_path ? <div className="grid gap-1 sm:grid-cols-[9rem_1fr]"><dt className="font-semibold">JSON path</dt><dd className="font-mono">{detail.json_path}</dd></div> : null}
            {detail.requirement ? <div className="grid gap-1 sm:grid-cols-[9rem_1fr]"><dt className="font-semibold">Requirement</dt><dd>{detail.requirement}</dd></div> : null}
            {detail.expected_format ? <div className="grid gap-1 sm:grid-cols-[9rem_1fr]"><dt className="font-semibold">Expected format</dt><dd className="whitespace-pre-wrap">{detail.expected_format}</dd></div> : null}
          </dl>
        ) : null}
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

function CheckStatus({ status, interrupted }: Readonly<{ status: ValidationCheckResponse['status']; interrupted: boolean }>) {
  if (interrupted && ['PENDING', 'RUNNING'].includes(status)) return <span className="text-slate-600">Unconfirmed</span>
  const tone = status === 'PASSED' ? 'text-emerald-700' : status === 'FAILED' ? 'text-red-700' : status === 'RUNNING' ? 'text-blue-700' : 'text-slate-500'
  const icon = status === 'PASSED' ? <CheckCircleIcon className="h-5 w-5 flex-none" aria-hidden="true" /> : status === 'FAILED' ? <XCircleIcon className="h-5 w-5 flex-none" aria-hidden="true" /> : status === 'RUNNING' ? <ArrowPathIcon className="h-5 w-5 flex-none animate-spin" aria-hidden="true" /> : <span className="h-2 w-2 flex-none rounded-full bg-current" aria-hidden="true" />
  return <span className={`inline-flex flex-col items-start gap-1 font-semibold sm:flex-row sm:items-center sm:gap-2 ${tone}`}>{icon}{labels[status]}</span>
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

export function RegistrationValidationChecks({ checks, interrupted = false }: Readonly<{ checks: ValidationCheckResponse[]; interrupted?: boolean }>) {
  const [expanded, setExpanded] = useState(true)
  const contentId = useId()
  const failedCount = checks.filter(check => check.id !== 'datasets' && check.status === 'FAILED').length

  return <div className="mt-6 text-sm">
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
      <div>
        <h3 className="font-semibold text-slate-700">Validation checks</h3>
        {failedCount > 0 ? <p className="mt-1 text-red-700">{failedCount} failed {failedCount === 1 ? 'check' : 'checks'}</p> : null}
      </div>
      <button
        aria-controls={contentId}
        aria-expanded={expanded}
        aria-label={`${expanded ? 'Collapse' : 'Expand'} validation checks`}
        className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg px-3 font-semibold text-blue-700 hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        onClick={() => setExpanded(current => !current)}
        type="button"
      >
        {expanded ? 'Collapse checks' : 'Expand checks'}
        <ChevronDownIcon aria-hidden="true" className={`h-5 w-5 ${expanded ? 'rotate-180' : ''}`} />
      </button>
    </div>
    <div hidden={!expanded} id={contentId}>
      <table className="mt-3 w-full table-fixed text-left">
        <caption className="sr-only">Validation status and schema or validator used for each check</caption>
        <thead className="border-b border-slate-200 text-sm text-slate-600"><tr>
          <th className="w-[42%] px-2 py-3 font-semibold sm:w-[40%]" scope="col">Validation</th>
          <th className="w-[25%] px-2 py-3 font-semibold sm:w-[20%]" scope="col">Status</th>
          <th className="px-2 py-3 font-semibold" scope="col">Schema / validator</th>
        </tr></thead>
        {checks.map(check => {
          const details = registrationValidationDetails({ validation_errors: check.errors, validation_details: check.validation_details })
          return <tbody className="border-b border-slate-100" key={check.id} data-check-id={check.id}>
            <tr className="align-top">
              <th className={`break-words px-2 py-4 font-medium text-slate-800 ${check.parent_id ? 'pl-5' : ''}`} scope="row">
                {check.dataset_index !== undefined && check.dataset_index !== null ? <span className="mb-1 block text-xs text-slate-500">Dataset {check.dataset_index + 1}</span> : null}
                {check.name}
                {check.description ? <span className="mt-1 block text-xs font-normal text-slate-500">{check.description}</span> : null}
              </th>
              <td className="px-2 py-4"><CheckStatus status={check.status} interrupted={interrupted} /></td>
              <td className="break-words px-2 py-4"><CheckProvenance check={check} /></td>
            </tr>
            {check.reason || details.length ? <tr><td className="px-2 pb-4" colSpan={3}>
              {check.reason ? <p className="mb-2 text-slate-600">{check.reason}</p> : null}
              {details.length ? <div><h4 className="mb-2 font-semibold text-slate-700">Validation errors ({details.length})</h4><DiagnosticErrors details={details} unavailableLocation /></div> : null}
            </td></tr> : null}
          </tbody>
        })}
      </table>
    </div>
  </div>
}
