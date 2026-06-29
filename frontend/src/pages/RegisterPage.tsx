import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRightIcon, CheckCircleIcon, CheckIcon, ExclamationTriangleIcon, PlusIcon, XMarkIcon } from '@heroicons/react/24/outline'
import type { AuthUser } from '../components/AppHeader'
import {
  createRegistrationApiV1RegistrationsPost,
  processRegistrationApiV1RegistrationsRegistrationIdProcessPost,
  revalidateRegistrationRouteApiV1RegistrationsRegistrationIdRevalidatePost,
  type RegistrationCreateResponse,
  type RegistrationProcessResponse,
  type RegistrationRevalidateResponse,
} from '../api/client'
import { client } from '../api/client/client.gen'
import { apiErrorMessage } from '../api/errors'

type RegisterPageProps = {
  authUser: AuthUser | null
}

type RegistrationForm = {
  adapterName: string
  repositoryLocation: string
  licenseValue: string
  doi: string
  cffUrl: string
}

type RegistrationResponse = RegistrationCreateResponse | RegistrationProcessResponse | RegistrationRevalidateResponse

type RegistrationResultPanelProps = {
  error: string | null
  isProcessing: boolean
  onRevalidate: () => void
  result: RegistrationResponse
}

type MetadataCheckStatus = 'idle' | 'checking' | 'found' | 'missing' | 'blocked'

const draftKey = 'bcr-register-draft'

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

// parse quickly on the client side to just keep the part we want to consistently look up the DOI record,
// whether they provide a link, or just the DOI directly.
// this takes the 2nd last slash until the end if present or the whole string otherwise.
function registrationDoiValue(value: string) {
  const trimmed = value.trim().replace(/^doi:\s*/i, '')
  if (!trimmed) return ''

  const cleanValue = trimmed.split(/[?#]/)[0].replace(/\/+$/, '')
  const parts = cleanValue.split('/').filter(Boolean)
  return /^https?:\/\//i.test(cleanValue) && parts.length >= 2
    ? parts.slice(-2).join('/')
    : cleanValue.replace(/^\/+/, '')
}

function initialForm(): RegistrationForm {
  const savedDraft = window.localStorage.getItem(draftKey)
  if (!savedDraft) {
    return emptyForm
  }

  try {
    return { ...emptyForm, ...(JSON.parse(savedDraft) as Partial<RegistrationForm>) }
  } catch {
    window.localStorage.removeItem(draftKey)
    return emptyForm
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
  const validationErrors = ('validation_errors' in result ? result.validation_errors : null)?.filter(Boolean) ?? []

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm md:p-10">
      <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div className="flex gap-4">
          <span
            className={`flex h-14 w-14 flex-none items-center justify-center rounded-full ${
              isValid
                ? 'bg-emerald-100 text-emerald-600'
                : isInvalid
                  ? 'bg-red-100 text-red-600'
                  : 'bg-amber-100 text-amber-700'
            }`}
          >
            {isValid ? (
              <CheckCircleIcon className="h-8 w-8" aria-hidden="true" />
            ) : (
              <ExclamationTriangleIcon className="h-8 w-8" aria-hidden="true" />
            )}
          </span>
          <span>
            <h2 className="text-2xl font-bold text-slate-950">
              {isValid
                ? 'Adapter registration successful'
                : isInvalid
                  ? 'Sorry, your adapter is not currently valid.'
                  : 'Registration submitted'}
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              {isValid
                ? `${result.adapter_name} was stored and validated by the registry.`
                : isInvalid
                  ? 'Please fix these issues in your GitHub repository, then revalidate.'
                  : `${result.adapter_name} was stored. Processing feedback is shown below.`}
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

function RegisterPage({ authUser }: RegisterPageProps) {
  const [form, setForm] = useState<RegistrationForm>(initialForm)
  const [status, setStatus] = useState<'idle' | 'submitting' | 'processing'>('idle')
  const [result, setResult] = useState<RegistrationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [metadataCheckStatus, setMetadataCheckStatus] = useState<MetadataCheckStatus>('idle')

  function updateField(field: keyof RegistrationForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const metadataCheckText =
    metadataCheckStatus === 'found'
      ? 'has croissant file'
      : metadataCheckStatus === 'missing'
        ? 'missing croissant file'
        : metadataCheckStatus === 'blocked'
          ? 'CORS blocked'
          : 'checking file'
  const metadataCheckClass =
    metadataCheckStatus === 'found'
      ? 'bg-emerald-400 text-white'
      : metadataCheckStatus === 'missing'
        ? 'bg-red-500 text-white'
        : metadataCheckStatus === 'blocked'
          ? 'bg-amber-400 text-slate-950'
          : 'bg-blue-100 text-blue-700'

  useEffect(() => {
    const location = form.repositoryLocation.trim().replace(/\/+$/, '')
    if (!/^https?:\/\/.+/.test(location)) return

    const controller = new AbortController()
    let repositoryUrl: URL
    try {
      repositoryUrl = new URL(location)
    } catch {
      return
    }
    const parts = repositoryUrl.pathname.split('/').filter(Boolean)
    const isGitHub = repositoryUrl.hostname === 'github.com' && parts.length >= 2
    const branch = isGitHub && parts[2] === 'blob' && parts[3] ? parts[3] : 'main'
    const path = isGitHub && parts[2] === 'blob' ? parts.slice(4).join('/') : 'croissant.jsonld'
    const metadataUrl = isGitHub
      ? `https://raw.githubusercontent.com/${parts[0]}/${parts[1]}/${branch}/${path}`
      : new URL('croissant.jsonld', location + '/').href

    void fetch(metadataUrl, { signal: controller.signal })
      .then((response) => {
        setMetadataCheckStatus(response.ok ? 'found' : response.status === 404 ? 'missing' : 'blocked')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setMetadataCheckStatus('blocked')
      })

    return () => controller.abort()
  }, [form.repositoryLocation])

  async function submitRegistration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setResult(null)

    const doi = registrationDoiValue(form.doi)

    if (!authUser) {
      window.localStorage.setItem(draftKey, JSON.stringify({ ...form, doi }))
      window.location.href = client.buildUrl({ url: '/api/v1/auth/github/start', query: { return_to: '/register' } })
      return
    }

    setStatus('submitting')
    try {
      const registrationResult = await createRegistrationApiV1RegistrationsPost({
        body: {
          adapter_name: form.adapterName,
          repository_location: form.repositoryLocation,
          license_value: form.licenseValue.trim() || undefined,
          doi: doi || undefined,
          cff_url: form.cffUrl.trim() || undefined,
        },
      })

      if (registrationResult.error || !registrationResult.data) {
        setStatus('idle')
        setError(apiErrorMessage(registrationResult.error, 'Registration failed.'))
        return
      }

      const registration = registrationResult.data
      window.localStorage.removeItem(draftKey)
      setStatus('processing')

      const processResult = await processRegistrationApiV1RegistrationsRegistrationIdProcessPost({
        path: { registration_id: registration.registration_id },
      })

      setStatus('idle')
      if (processResult.error || !processResult.data) {
        setResult(registration)
        setError(apiErrorMessage(processResult.error, 'Registration was saved, but processing failed.'))
        return
      }

      setResult(processResult.data)
    } catch (error) {
      setStatus('idle')
      setError(apiErrorMessage(error, 'Registration failed.'))
    }
  }

  async function revalidateRegistration() {
    if (!result) return

    setStatus('processing')
    setError(null)
    try {
      const revalidateResult = await revalidateRegistrationRouteApiV1RegistrationsRegistrationIdRevalidatePost({
        path: { registration_id: result.registration_id },
      })

      setStatus('idle')
      if (revalidateResult.error || !revalidateResult.data) {
        setError(apiErrorMessage(revalidateResult.error, 'Revalidation failed.'))
        return
      }

      setResult(revalidateResult.data)
    } catch (error) {
      setStatus('idle')
      setError(apiErrorMessage(error, 'Revalidation failed.'))
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
                Adapter name*
                <input
                  className="h-14 rounded-xl border border-slate-200 bg-slate-50 px-5 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
                  onChange={(event) => updateField('adapterName', event.target.value)}
                  placeholder="Example: Clinical Visit Adapter"
                  required
                  type="text"
                  value={form.adapterName}
                />
              </label>

              <label className="grid gap-3 text-sm font-semibold text-slate-950">
                Repository location*
                <span className="relative block">
                  <input
                    className="h-14 w-full rounded-xl border border-slate-200 bg-slate-50 px-5 pr-48 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
                    onChange={(event) => {
                      const value = event.target.value
                      setError(null)
                      setMetadataCheckStatus(/^https?:\/\/.+/.test(value.trim()) ? 'checking' : 'idle')
                      updateField('repositoryLocation', value)
                    }}
                    placeholder="https://github.com/example/clinical-visit-adapter"
                    required
                    type="url"
                    value={form.repositoryLocation}
                  />
                  {metadataCheckStatus !== 'idle' ? (
                    <span
                      aria-live="polite"
                      className={`pointer-events-none absolute right-1.5 top-1/2 inline-flex h-12 -translate-y-1/2 items-center gap-2 rounded-2xl px-4 text-sm font-medium ${metadataCheckClass}`}
                    >
                      {metadataCheckStatus === 'found' ? (
                        <CheckIcon className="h-5 w-5" aria-hidden="true" />
                      ) : metadataCheckStatus === 'missing' ? (
                        <XMarkIcon className="h-5 w-5" aria-hidden="true" />
                      ) : metadataCheckStatus === 'blocked' ? (
                        <ExclamationTriangleIcon className="h-5 w-5" aria-hidden="true" />
                      ) : (
                        <span className="h-2.5 w-2.5 rounded-full bg-current" aria-hidden="true" />
                      )}
                      {metadataCheckText}
                    </span>
                  ) : null}
                </span>
              </label>

              <label className="grid gap-3 text-sm font-semibold text-slate-950">
                License
                <input
                  className="h-14 rounded-xl border border-slate-200 bg-slate-50 px-5 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
                  onChange={(event) => updateField('licenseValue', event.target.value)}
                  placeholder="MIT"
                  type="text"
                  value={form.licenseValue}
                />
              </label>

              <label className="grid gap-3 text-sm font-semibold text-slate-950">
                DOI
                <input
                  className="h-14 rounded-xl border border-slate-200 bg-slate-50 px-5 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
                  onBlur={(event) => updateField('doi', registrationDoiValue(event.target.value))}
                  onChange={(event) => updateField('doi', event.target.value)}
                  placeholder="10.1000/182"
                  type="text"
                  value={form.doi}
                />
              </label>

              <label className="grid gap-3 text-sm font-semibold text-slate-950">
                CFF file link
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
                We use GitHub to attach your login to the registration.
              </p>
              <button
                className="inline-flex h-14 min-w-56 cursor-pointer items-center justify-center gap-3 rounded-lg bg-slate-950 px-6 text-base font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
                disabled={status !== 'idle'}
                type="submit"
              >
                {status === 'submitting'
                  ? 'Submitting...'
                  : status === 'processing'
                    ? 'Checking adapter'
                    : authUser
                      ? 'Register adapter'
                      : 'Sign in with GitHub'}
                {authUser ? (
                  <PlusIcon className="h-5 w-5" aria-hidden="true" />
                ) : (
                  <ArrowRightIcon className="h-5 w-5" aria-hidden="true" />
                )}
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
