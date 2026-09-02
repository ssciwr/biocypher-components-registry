import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import { ArrowRightIcon, CheckCircleIcon, CheckIcon, ExclamationTriangleIcon, PlusIcon, XMarkIcon } from '@heroicons/react/24/outline'
import type { AuthUser } from '../components/AppHeader'
import { RepositoryUrlInput } from '../components/RepositoryUrlInput'
import {
  createRegistrationApiV1RegistrationsPost,
  processRegistrationApiV1RegistrationsRegistrationIdProcessPost,
  revalidateRegistrationRouteApiV1RegistrationsRegistrationIdRevalidatePost,
  type RegistrationCreateResponse,
  type RegistrationProcessResponse,
  type RegistrationRevalidateResponse,
} from '../api/client'
import { client } from '../api/client/client.gen'
import { fetchCrossrefWork } from '../api/crossref'

type RegisterPageProps = Readonly<{
  authVerified: boolean
  authUser: AuthUser | null
}>

type RegistrationForm = {
  adapterName: string
  repositoryLocation: string
  licenseValue: string
  doi: string
  cffUrl: string
}

type RegistrationResponse = RegistrationCreateResponse | RegistrationProcessResponse | RegistrationRevalidateResponse

type RegistrationResultPanelProps = Readonly<{
  error: string | null
  isProcessing: boolean
  onRevalidate: () => void
  result: RegistrationResponse
}>

type RegistrationResultDisplay = Readonly<{
  iconTone: string
  text: string
  title: string
}>

type InlineStatusDisplay = Readonly<{
  className: string
  icon: ReactNode
  text: string
}>

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
const submitStatusText: Record<'processing' | 'submitting', string> = {
  processing: 'Checking adapter',
  submitting: 'Submitting...',
}

const emptyForm: RegistrationForm = {
  adapterName: '',
  repositoryLocation: '',
  licenseValue: '',
  doi: '',
  cffUrl: '',
}

const nextSteps = [
  {
    title: 'Source is stored',
    text: 'A registration source record is created',
  },
  {
    title: 'Discovery checks root file',
    text: 'The registry looks for croissant.jsonld',
  },
  {
    title: 'Validation',
    text: 'We ensure the croissant file is valid',
  },
  {
    title: 'Review',
    text: 'The BioCypher team will review your adapter submission',
  },
]

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
function registrationResultFeedbackDisplay(result: RegistrationResponse): RegistrationResultDisplay {
  // AI-generated helper which groups semantically the relevant icon tone, title and text for registraiton feedback
  if (result.status === 'VALID') {
    return {
      iconTone: 'bg-emerald-100 text-emerald-600',
      text: `${result.adapter_name} was stored and validated by the registry.`,
      title: 'Adapter registration successful',
    }
  }

  if (result.status === 'INVALID') {
    return {
      iconTone: 'bg-red-100 text-red-600',
      text: 'Please fix these issues in your GitHub repository, then revalidate.',
      title: 'Sorry, your adapter is not currently valid.',
    }
  }

  return {
    iconTone: 'bg-amber-100 text-amber-700',
    text: `${result.adapter_name} was stored. Processing feedback is shown below.`,
    title: 'Registration submitted',
  }
}

// Basically this shows errors or successful registration
function RegistrationResultPanel({
  error,
  isProcessing,
  onRevalidate,
  result,
}: RegistrationResultPanelProps) {
  const isValid = result.status === 'VALID'
  const isInvalid = result.status === 'INVALID'
  const resultDisplay = registrationResultFeedbackDisplay(result)
  const validationErrors = ('validation_errors' in result ? result.validation_errors : null)?.filter(Boolean) ?? []

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm md:p-10">
      <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div className="flex gap-4">
          <span
            className={`flex h-14 w-14 flex-none items-center justify-center rounded-full ${resultDisplay.iconTone}`}
          >
            {isValid ? (
              <CheckCircleIcon className="h-8 w-8" aria-hidden="true" />
            ) : (
              <ExclamationTriangleIcon className="h-8 w-8" aria-hidden="true" />
            )}
          </span>
          <span>
            <h2 className="text-2xl font-bold text-slate-950">
              {resultDisplay.title}
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              {resultDisplay.text}
            </p>
          </span>
        </div>

        {isInvalid ? (
          <button
            className="inline-flex h-12 min-w-40 cursor-pointer items-center justify-center rounded-lg bg-blue-600 px-5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
            disabled={isProcessing}
            onClick={onRevalidate}
            type="button"
          >
            {isProcessing ? 'Revalidating...' : 'Revalidate'}
          </button>
        ) : null}
      </div>

      <dl className="mt-8 grid gap-4 border-t border-slate-100 pt-6 text-sm md:grid-cols-3">
        <div>
          <dt className="font-semibold text-slate-500">Status</dt>
          <dd className="mt-1 font-bold text-slate-950">{result.status}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">Repository</dt>
          <dd className="mt-1 break-all text-slate-950">{result.repository_location}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">Registration ID</dt>
          <dd className="mt-1 break-all text-slate-950">{result.registration_id}</dd>
        </div>
      </dl>

      {validationErrors.length > 0 ? (
        <ul className="mt-6 grid gap-3">
          {validationErrors.map((validationError, index) => (
            <li
              className="rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700"
              key={`${validationError}-${index}`}
            >
              {validationError}
            </li>
          ))}
        </ul>
      ) : null}

      {isInvalid && validationErrors.length === 0 ? (
        <p className="mt-6 rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          The backend marked this registration invalid without detailed validation errors.
        </p>
      ) : null}

      {error ? (
        <p className="mt-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {error}
        </p>
      ) : null}
    </section>
  )
}

function RegisterPage({ authVerified, authUser }: RegisterPageProps) { // NOSONAR: this page coordinates one registration workflow; splitting it is a larger UI refactor.
  const autoSubmitAttemptedRef = useRef(false)
  const [form, setForm] = useState<RegistrationForm>(initialForm)
  const [status, setStatus] = useState<'idle' | 'submitting' | 'processing'>('idle')
  const [result, setResult] = useState<RegistrationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [doiCheck, setDoiCheck] = useState<{ status: DoiCheckStatus; value: string }>({ status: 'idle', value: '' })

  function updateField(field: keyof RegistrationForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const doiCheckStatus = doiCheck.value === registrationDoiValue(form.doi) ? doiCheck.status : 'idle' // reactive prop
  const doiCheckDisplay = doiCheckDisplays[doiCheckStatus]
  const canSubmitDirectly = Boolean(authUser)
  const idleSubmitButtonText = canSubmitDirectly ? 'Register adapter' : 'Sign in with GitHub'
  const submitButtonText = status === 'idle' ? idleSubmitButtonText : submitStatusText[status]
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

  const submitAuthenticatedRegistration = useCallback(async (registrationForm: RegistrationForm) => {
    setError(null)
    setResult(null)

    const doi = registrationDoiValue(registrationForm.doi)

    setStatus('submitting')
    try {
      const registrationResult = await createRegistrationApiV1RegistrationsPost({
        body: {
          adapter_name: registrationForm.adapterName,
          repository_location: registrationForm.repositoryLocation,
          license_value: registrationForm.licenseValue.trim() || undefined,
          doi: doi || undefined,
          cff_url: registrationForm.cffUrl.trim() || undefined,
        },
      })

      const registrationError = registrationResult.error as unknown
      if (registrationError || !registrationResult.data) {
        const details = registrationError as { details?: string; detail?: string } | undefined
        setStatus('idle')
        setError(
          typeof registrationError === 'string' && registrationError
            ? registrationError
            : details?.details || details?.detail || 'Registration failed.'
        )
        return
      }

      const registration = registrationResult.data
      globalThis.localStorage.removeItem(draftKey)
      globalThis.localStorage.removeItem(submitAfterAuthKey)
      setStatus('processing')

      const processResult = await processRegistrationApiV1RegistrationsRegistrationIdProcessPost({
        path: { registration_id: registration.registration_id }, // NOSONAR: we ignore this in SONAR because the registration ID comes from our backend response, and it only goes into an already host-specified generated API request back to our own backend. If it is bad, the user only gets a not found or failed processing request.
      })

      setStatus('idle')
      const processError = processResult.error as unknown
      if (processError || !processResult.data) {
        const details = processError as { details?: string; detail?: string } | undefined
        setResult(registration)
        setError(
          typeof processError === 'string' && processError
            ? processError
            : details?.details || details?.detail || 'Registration was saved, but processing failed.'
        )
        return
      }

      setResult(processResult.data)
    } catch (error) {
      const details = error as { details?: string; detail?: string } | undefined
      setStatus('idle')
      setError(
        typeof error === 'string' && error
          ? error
          : details?.details || details?.detail || 'Registration failed.'
      )
    }
  }, [])

  useEffect(() => {
    if (!authVerified || !authUser || autoSubmitAttemptedRef.current || result || status !== 'idle') return
    if (globalThis.localStorage.getItem(submitAfterAuthKey) !== '1') return

    const submitTimer = globalThis.setTimeout(() => {
      if (autoSubmitAttemptedRef.current) return
      autoSubmitAttemptedRef.current = true
      globalThis.localStorage.removeItem(submitAfterAuthKey)
      void submitAuthenticatedRegistration(form)
    }, 0)
    return () => globalThis.clearTimeout(submitTimer)
  }, [authUser, authVerified, form, result, status, submitAuthenticatedRegistration])

  async function submitRegistration(event: { preventDefault: () => void }) {
    event.preventDefault()

    const doi = registrationDoiValue(form.doi)

    if (!authUser) {
      globalThis.localStorage.setItem(draftKey, JSON.stringify({ ...form, doi }))
      globalThis.localStorage.setItem(submitAfterAuthKey, '1')
      globalThis.location.href = client.buildUrl({ url: '/api/v1/auth/github/start', query: { return_to: '/register' } })
      return
    }

    await submitAuthenticatedRegistration({ ...form, doi })
  }

  async function revalidateRegistration() {
    if (!result) return

    setStatus('processing')
    setError(null)
    try {
      const revalidateResult = await revalidateRegistrationRouteApiV1RegistrationsRegistrationIdRevalidatePost({
        path: { registration_id: result.registration_id }, // NOSONAR: we ignore this in SONAR because the registration ID comes from our backend response, and it only goes into an already host-specified generated API request back to our own backend. If it is bad, the user only gets a not found or failed revalidation request.
      })

      setStatus('idle')
      const revalidateError = revalidateResult.error as unknown
      if (revalidateError || !revalidateResult.data) {
        const details = revalidateError as { details?: string; detail?: string } | undefined
        setError(
          typeof revalidateError === 'string' && revalidateError
            ? revalidateError
            : details?.details || details?.detail || 'Revalidation failed.'
        )
        return
      }

      setResult(revalidateResult.data)
    } catch (error) {
      const details = error as { details?: string; detail?: string } | undefined
      setStatus('idle')
      setError(
        typeof error === 'string' && error
          ? error
          : details?.details || details?.detail || 'Revalidation failed.'
      )
    }
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

        {result ? (
          <RegistrationResultPanel
            error={error}
            isProcessing={status === 'processing'}
            onRevalidate={() => void revalidateRegistration()}
            result={result}
          />
        ) : (
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_410px]">
            <form
              className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm md:p-10"
              onSubmit={submitRegistration}
            >
            <h2 className="text-2xl font-bold text-slate-950">Registration details</h2>

            <div className="mt-8 grid gap-6">
              <label className="grid gap-3 text-sm font-semibold text-slate-950">
                <span>Adapter name*</span>
                <input
                  className="h-14 rounded-xl border border-slate-200 bg-slate-50 px-5 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
                  onChange={(event) => updateField('adapterName', event.target.value)}
                  placeholder="Example: Clinical Visit Adapter"
                  required
                  type="text"
                  value={form.adapterName}
                />
              </label>

              <RepositoryUrlInput
                inputClassName="h-14 rounded-xl border border-slate-200 bg-slate-50 px-5 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
                label={<>Repository location <small>(Any repository url, GitHub, GitLab, etc.)*</small></>}
                labelClassName="grid gap-3 text-sm font-semibold text-slate-950"
                onChange={(value) => {
                  setError(null)
                  updateField('repositoryLocation', value)
                }}
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
                className="inline-flex h-14 min-w-56 cursor-pointer items-center justify-center gap-3 rounded-lg bg-slate-950 px-6 text-base font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
                disabled={status !== 'idle'}
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
