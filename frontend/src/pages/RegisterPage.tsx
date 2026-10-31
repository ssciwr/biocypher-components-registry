import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import { ArrowPathIcon, ArrowRightIcon, CheckCircleIcon, CheckIcon, ExclamationTriangleIcon, PlusIcon, XMarkIcon } from '@heroicons/react/24/outline'
import type { AuthUser } from '../components/AppHeader'
import { RepositoryUrlInput } from '../components/RepositoryUrlInput'
import {
  type RegistrationAttemptResponse,
  type ValidationCheckResponse,
} from '../api/client'
import { client } from '../api/client/client.gen'
import { fetchCrossrefWork } from '../api/crossref'
import { RegistrationRequestRejectedError, submitRegistrationStream } from '../api/registration'
import { DiagnosticErrors, RegistrationValidationChecks } from '../components/RegistrationValidationChecks'
import { registrationValidationDetails } from '../api/validationDiagnostics'

type RegisterPageProps = Readonly<{
  authVerified: boolean
  authUser: AuthUser | null
}>

type RegistrationForm = {
  repositoryLocation: string
  licenseValue: string
  doi: string
  cffUrl: string
}

type RegistrationResponse = RegistrationAttemptResponse

type RegistrationResultPanelProps = Readonly<{
  isProcessing: boolean
  isRetrying: boolean
  onRetry: () => void
  repositoryLocation: string
  result: RegistrationResponse | null
  checks: ValidationCheckResponse[]
  error: string | null
}>

type InlineStatusDisplay = Readonly<{ className: string; icon: ReactNode; text: string }>

type DoiCheckStatus = 'idle' | 'checking' | 'found' | 'missing' | 'error'

const draftKey = 'bcr-register-draft'
const submitAfterAuthKey = 'bcr-register-submit-after-auth'
const pendingStatusIcon = (
  <span className="h-2.5 w-2.5 rounded-full bg-current" aria-hidden="true" />
)
const checkStatusIcon = <CheckIcon className="h-5 w-5" aria-hidden="true" />
const failedStatusIcon = <XMarkIcon className="h-5 w-5" aria-hidden="true" />
const doiCheckDisplays: Record<DoiCheckStatus, InlineStatusDisplay> = {
  idle: { className: 'text-blue-700', icon: failedStatusIcon, text: 'checking Crossref' },
  checking: { className: 'text-blue-700', icon: pendingStatusIcon, text: 'checking Crossref' },
  found: { className: 'text-emerald-600', icon: checkStatusIcon, text: 'DOI found in Crossref' },
  missing: { className: 'text-red-600', icon: failedStatusIcon, text: 'DOI not found in Crossref. Make sure it fits this format: 10.1000/182' },
  error: { className: 'text-red-600', icon: failedStatusIcon, text: 'Could not check DOI' },
}


const emptyForm: RegistrationForm = {
  repositoryLocation: '',
  licenseValue: '',
  doi: '',
  cffUrl: '',
}

const nextSteps = [
  { title: 'Check the repository', text: 'We check for croissant.jsonld at the repository root.' },
  { title: 'Validate the metadata', text: 'Registration fetches the latest metadata and validates it.' },
  { title: 'Publish accepted metadata', text: 'Your adapter is saved only after validation succeeds.' },
  { title: 'Fix and retry if needed', text: 'Failed first registrations are not saved. Correct the reported issues and retry.' },
]

const registrationFailureReasons: Record<string, string> = {
  INVALID_JSON: 'Invalid JSON',
  SCHEMA_INVALID: 'Schema validation failed',
  MLCROISSANT_INVALID: 'Croissant validation failed',
  SEMANTICS_INVALID: 'Invalid metadata structure',
  METADATA_NOT_FOUND: 'Croissant file not found',
  REPOSITORY_UNAVAILABLE: 'Repository unavailable',
  REMOTE_TEMPORARY: 'Repository host temporarily unavailable',
  DEFAULT_BRANCH_UNRESOLVED: 'Default branch could not be resolved',
  GIT_FILTER_UNSUPPORTED: 'Repository host unsupported',
  METADATA_TOO_LARGE: 'Metadata file too large',
  ADAPTER_ID_CHANGED: 'Adapter identity changed',
  VERSION_NOT_BUMPED: 'Version not changed',
  DUPLICATE: 'Adapter already registered',
}

function registrationDoiValue(value: string) {
  const trimmed = value.trim()
  return trimmed.toLowerCase().startsWith('doi:')
    ? trimmed.slice(4).trimStart()
    : trimmed
}

function initialForm(): RegistrationForm {
  const savedDraft = globalThis.localStorage.getItem(draftKey)
  if (!savedDraft) {
    return emptyForm
  }

  try {
    return { ...emptyForm, ...(JSON.parse(savedDraft) as Partial<RegistrationForm>) }
  } catch (error) {
    console.error('Could not read registration draft.', error)
    globalThis.localStorage.removeItem(draftKey)
    globalThis.localStorage.removeItem(submitAfterAuthKey)
    return emptyForm
  }
}

/*
 * AI-Generated. Based on the Penpot designs.
 */

function RegistrationResultPanel({
  isProcessing,
  isRetrying,
  onRetry,
  repositoryLocation,
  result,
  checks,
  error,
}: RegistrationResultPanelProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const succeeded = result?.attempt_status === 'SUCCEEDED'
  const failed = result?.attempt_status === 'FAILED'
  const groupedDetails = checks.flatMap(check => registrationValidationDetails({ validation_errors: check.errors, validation_details: check.validation_details }))
  const validationDetails = registrationValidationDetails(result).filter(detail => !groupedDetails.some(grouped => grouped.message.trim() === detail.message.trim()))
  const showMessage = Boolean(result?.message.trim()) && ![...validationDetails, ...groupedDetails].some((detail) => detail.message.trim() === result?.message.trim())
  const failureReason = registrationFailureReasons[result?.reason_code ?? ''] ?? 'Not registered'
  const registrationStatus = error ? 'UNCONFIRMED - Registration outcome unknown' : isProcessing ? 'PROCESSING - Checking metadata' : succeeded ? 'SUCCEEDED - Registered' : `FAILED - ${failureReason}`
  const repository = result?.repository_location ?? repositoryLocation
  const title = error ? 'Registration outcome could not be confirmed' : isProcessing ? 'Checking your adapter...' : succeeded ? 'Adapter registered successfully' : 'Registration failed'
  const iconTone = isProcessing ? 'bg-blue-100 text-blue-600' : succeeded ? 'bg-emerald-100 text-emerald-600' : 'bg-red-100 text-red-600'

  useEffect(() => {
    headingRef.current?.focus()
  }, [isProcessing, result])

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm md:p-10" role="status" aria-busy={isProcessing}>
      <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div className="flex items-start gap-4">
          <span className={`flex h-14 w-14 flex-none items-center justify-center rounded-full ${iconTone}`}>
            {isProcessing ? <ArrowPathIcon className="h-8 w-8 animate-spin" aria-hidden="true" /> : succeeded ? <CheckCircleIcon className="h-8 w-8" aria-hidden="true" /> : <ExclamationTriangleIcon className="h-8 w-8" aria-hidden="true" />}
          </span>
          <div>
            <h2 className="text-2xl font-bold text-slate-950 outline-none" ref={headingRef} tabIndex={-1}>{title}</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              {error ? error : isProcessing ? 'Fetching and validating croissant.jsonld from your repository.' : succeeded ? result?.message : 'Your adapter has not been registered yet. Review the details, fix the issues in your repository, then retry.'}
            </p>
          </div>
        </div>
        {failed || (isProcessing && isRetrying) ? (
          <div className="flex flex-wrap gap-3">
            <button className="inline-flex h-12 min-w-40 cursor-pointer items-center justify-center rounded-lg bg-blue-600 px-5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400" disabled={isProcessing} onClick={onRetry} type="button">
              {isProcessing ? 'Retrying...' : 'Retry registration'}
            </button>
          </div>
        ) : null}
      </div>
      <dl className="mt-8 grid gap-4 border-t border-slate-100 pt-6 text-sm md:grid-cols-3">
        <div><dt className="font-semibold text-slate-500">Registration status</dt><dd className="mt-1 font-bold">{registrationStatus}</dd></div>
        <div><dt className="font-semibold text-slate-500">Repository</dt><dd className="mt-1 break-all">{repository}</dd></div>
        {failed ? <div><dt className="font-semibold text-slate-500">Reason code</dt><dd className="mt-1 break-words">{result.reason_code ?? 'Not provided'}</dd></div> : null}
        {succeeded ? <div><dt className="font-semibold text-slate-500">Current version</dt><dd className="mt-1">{result?.published_version}</dd></div> : null}
      </dl>
      {checks.length ? <RegistrationValidationChecks checks={checks} interrupted={Boolean(error)} /> : null}
      {failed ? (
        <div className="mt-6 grid gap-6 text-sm">
          {showMessage ? <div className="rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-red-700">
            <h3 className="font-semibold">Message</h3>
            <p className="mt-1 whitespace-pre-wrap break-words">{result.message}</p>
          </div> : null}
          {validationDetails.length > 0 ? <div>
            <h3 className="font-semibold text-slate-700">Validation errors ({validationDetails.length})</h3>
            <div className="mt-3"><DiagnosticErrors details={validationDetails} /></div>
          </div> : null}
          {!showMessage && validationDetails.length === 0 && groupedDetails.length === 0 ? <p className="text-slate-600">No additional diagnostic information was returned.</p> : null}
        </div>
      ) : null}
    </section>
  )
}

function RegisterPage({ authVerified, authUser }: RegisterPageProps) { // NOSONAR: this page coordinates one registration workflow; splitting it is a larger UI refactor.
  const autoSubmitAttemptedRef = useRef(false)
  const submissionRef = useRef<AbortController | null>(null)
  const [checks, setChecks] = useState<ValidationCheckResponse[]>([])
  const [unconfirmed, setUnconfirmed] = useState(false)
  useEffect(() => () => submissionRef.current?.abort(), [])
  const [form, setForm] = useState<RegistrationForm>(initialForm)
  const [status, setStatus] = useState<'idle' | 'processing'>('idle')
  const [result, setResult] = useState<RegistrationResponse | null>(null)
  const [isRetrying, setIsRetrying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasCroissantFile, setHasCroissantFile] = useState(false)
  const [doiCheck, setDoiCheck] = useState<{ status: DoiCheckStatus; value: string }>({ status: 'idle', value: '' })

  function updateField(field: keyof RegistrationForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const doiCheckStatus = doiCheck.value === registrationDoiValue(form.doi) ? doiCheck.status : 'idle' // reactive prop
  const doiCheckDisplay = doiCheckDisplays[doiCheckStatus]
  const canSubmitDirectly = Boolean(authUser && authVerified)
  const idleSubmitButtonText = canSubmitDirectly ? 'Register adapter' : 'Sign in with GitHub'
  const submitButtonText = status === 'idle' ? idleSubmitButtonText : isRetrying ? 'Retrying...' : 'Registering...'
  const SubmitButtonIcon = canSubmitDirectly ? PlusIcon : ArrowRightIcon

  async function checkDoiOnBlur(value: string) {
    const doi = registrationDoiValue(value)
    updateField('doi', doi)
    setDoiCheck({ status: 'idle', value: doi })
    if (!doi) return

    setDoiCheck({ status: 'checking', value: doi })
    try {
      const work = await fetchCrossrefWork(doi)
      const status = work ? 'found' : 'missing'
      setDoiCheck((current) => (
        current.value === doi ? { status, value: doi } : current
      ))
    } catch (error) {
      console.error('Could not check DOI with Crossref.', error)
      setDoiCheck((current) => (
        current.value === doi ? { status: 'error', value: doi } : current
      ))
    }
  }

  const submitAuthenticatedRegistration = useCallback(async (registrationForm: RegistrationForm, retry = false) => {
    if (!hasCroissantFile || submissionRef.current) return
    const controller = new AbortController()
    submissionRef.current = controller
    setError(null)
    setResult(null)
    setChecks([])
    setUnconfirmed(false)
    setIsRetrying(retry)
    setStatus('processing')
    try {
      const outcome = await submitRegistrationStream({
        repository_location: registrationForm.repositoryLocation,
        license_value: registrationForm.licenseValue.trim() || undefined,
        doi: registrationDoiValue(registrationForm.doi) || undefined,
        cff_url: registrationForm.cffUrl.trim() || undefined,
      }, controller.signal, setChecks)
      if (controller.signal.aborted) return
      setResult(outcome)
      setChecks(outcome.validation_checks ?? [])
      if (outcome.attempt_status === 'SUCCEEDED') {
        globalThis.localStorage.removeItem(draftKey)
        globalThis.localStorage.removeItem(submitAfterAuthKey)
      }
    } catch (error) {
      if (controller.signal.aborted) return
      setUnconfirmed(!(error instanceof RegistrationRequestRejectedError))
      setError(error instanceof Error ? error.message : 'The connection ended before a final result arrived. Check the adapter list before trying again.')

    } finally {
      if (submissionRef.current === controller) submissionRef.current = null
      if (!controller.signal.aborted) setStatus('idle')
    }
  }, [hasCroissantFile])

  useEffect(() => {
    if (!hasCroissantFile) return
    if (!authVerified || !authUser || autoSubmitAttemptedRef.current || result || unconfirmed || status !== 'idle') return
    if (globalThis.localStorage.getItem(submitAfterAuthKey) !== '1') return

    globalThis.queueMicrotask(() => {
      if (autoSubmitAttemptedRef.current) return

      autoSubmitAttemptedRef.current = true
      globalThis.localStorage.removeItem(submitAfterAuthKey)
      void submitAuthenticatedRegistration(form)
    })
  }, [authUser, authVerified, form, hasCroissantFile, result, status, submitAuthenticatedRegistration, unconfirmed])

  async function submitRegistration(event: { preventDefault: () => void }) {
    event.preventDefault()
    if (!hasCroissantFile || status !== 'idle') return

    const doi = registrationDoiValue(form.doi)

    if (!canSubmitDirectly) {
      globalThis.localStorage.setItem(draftKey, JSON.stringify({ ...form, doi }))
      globalThis.localStorage.setItem(submitAfterAuthKey, '1')
      globalThis.location.href = client.buildUrl({ url: '/api/v1/auth/github/start', query: { return_to: '/register' } })
      return
    }

    await submitAuthenticatedRegistration({ ...form, doi })
  }


  return (
    <section className="bg-slate-100">
      <div className="mx-auto max-w-7xl px-6 py-16 md:py-20">
        <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center">
          <h1 className="text-4xl font-semibold tracking-normal text-slate-950 md:text-5xl">
            Register an adapter
          </h1>
          <span className="w-fit rounded-full bg-blue-100 px-6 py-3 text-sm text-blue-600">
            For adapter maintainers
          </span>
        </div>

        {result || unconfirmed || status === 'processing' ? (
          <RegistrationResultPanel
            isProcessing={status === 'processing'}
            isRetrying={isRetrying}
            onRetry={() => {
              if (status === 'idle' && canSubmitDirectly) void submitAuthenticatedRegistration(form, true)
            }}
            repositoryLocation={form.repositoryLocation.trim()}
            result={result}
            checks={checks}
            error={unconfirmed ? error : null}
          />
        ) : (
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_410px]">
            <form
              className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm md:p-10"
              onSubmit={submitRegistration}
            >
            <h2 className="text-2xl font-bold text-slate-950">Registration details</h2>

            <div className="mt-8 grid gap-6">
              <RepositoryUrlInput
                inputClassName="h-14 rounded-xl border border-slate-200 bg-slate-50 px-5 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
                label={<>Repository location <small>(Any repository url, GitHub, GitLab, etc.)*</small></>}
                labelClassName="grid gap-3 text-sm font-semibold text-slate-950"
                onChange={(value) => {
                  setError(null)
                  if (value.trim() !== form.repositoryLocation.trim()) setHasCroissantFile(false)
                  updateField('repositoryLocation', value)
                }}
                onValidationChange={setHasCroissantFile}
                placeholder="https://gitlab.institute.org/group/clinical-visit-adapter"
                required
                value={form.repositoryLocation}
              />

              <label className="grid gap-3 text-sm font-semibold text-slate-950">
                <span>License</span>
                <input
                  className="h-14 rounded-xl border border-slate-200 bg-slate-50 px-5 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
                  onChange={(event) => updateField('licenseValue', event.target.value)}
                  placeholder="MIT"
                  type="text"
                  value={form.licenseValue}
                />
              </label>

              <label className="grid gap-3 text-sm font-semibold text-slate-950">
                <span>DOI</span>
                <input
                  className="h-14 rounded-xl border border-slate-200 bg-slate-50 px-5 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
                  aria-invalid={doiCheckStatus === 'missing' || doiCheckStatus === 'error'}
                  onBlur={(event) => void checkDoiOnBlur(event.target.value)}
                  onChange={(event) => {
                    setDoiCheck({ status: 'idle', value: '' })
                    updateField('doi', event.target.value)
                  }}
                  placeholder="10.1000/182"
                  type="text"
                  value={form.doi}
                />
                {doiCheckStatus !== 'idle' ? (
                  <span
                    aria-live="polite"
                    className={`inline-flex items-center gap-2 text-sm font-medium ${doiCheckDisplay.className}`}
                  >
                    {doiCheckDisplay.icon}
                    {doiCheckDisplay.text}
                  </span>
                ) : null}
              </label>

              <label className="grid gap-3 text-sm font-semibold text-slate-950">
                <span>CFF file link</span>
                <input
                  className="h-14 rounded-xl border border-slate-200 bg-slate-50 px-5 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
                  onChange={(event) => updateField('cffUrl', event.target.value)}
                  placeholder="https://github.com/example/adapter/blob/main/CITATION.cff"
                  type="url"
                  value={form.cffUrl}
                />
              </label>
            </div>
            <div className="mt-10 flex flex-col gap-4 border-t border-slate-100 pt-8 md:flex-row md:items-center md:justify-end">
              <p className="text-sm leading-6 text-slate-500 md:max-w-sm md:text-right">
                Sign in once so we can attach your login to the registration.
              </p>
              <button
                className="inline-flex h-14 min-w-56 cursor-pointer items-center justify-center gap-3 rounded-lg bg-slate-950 px-6 text-base font-semibold text-white enabled:hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
                disabled={!hasCroissantFile || status !== 'idle'}
                type="submit"
              >
                {submitButtonText}
                <SubmitButtonIcon className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>

            {error ? (
              <p className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </p>
            ) : null}
          </form>

          <aside className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm md:p-10">
            <h2 className="text-2xl font-bold text-slate-950">What happens next?</h2>
            <ol className="mt-8 grid gap-8">
              {nextSteps.map((step, index) => (
                <li className="grid grid-cols-[44px_1fr] gap-5" key={step.title}>
                  <span className="flex h-11 w-11 items-center justify-center rounded-full bg-blue-100 text-base font-semibold text-blue-600">
                    {index + 1}
                  </span>
                  <span>
                    <span className="block text-base font-bold text-slate-950">{step.title}</span>
                    <span className="mt-1 block text-sm leading-5 text-slate-700">{step.text}</span>
                  </span>
                </li>
              ))}
            </ol>
          </aside>
          </div>
        )}
      </div>
    </section>
  )
}

export default RegisterPage
