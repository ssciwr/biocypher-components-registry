import { useEffect, useState } from 'react'
import type { ReactNode, SyntheticEvent } from 'react'
import { ArrowRightIcon, CheckCircleIcon, CheckIcon, ExclamationTriangleIcon, PlusIcon, XMarkIcon } from '@heroicons/react/24/outline'
import type { AuthUser } from '../components/AppHeader'

type RegisterPageProps = Readonly<{
  apiBaseUrl: string
  authUser: AuthUser | null
}>

type RegistrationForm = {
  adapterName: string
  repositoryLocation: string
  licenseValue: string
  doi: string
}

type RegistrationStatus = 'SUBMITTED' | 'VALID' | 'INVALID' | (string & {})

type RegistrationResponse = {
  registration_id: string
  adapter_name: string
  adapter_id: string
  repository_location: string
  status: RegistrationStatus
  validation_errors?: string[] | null
  submitted_by_github_login: string | null
}

type RegistrationResultPanelProps = Readonly<{
  error: string | null
  isProcessing: boolean
  onRevalidate: () => void
  result: RegistrationResponse
}>

type MetadataCheckStatus = 'idle' | 'checking' | 'found' | 'missing' | 'blocked'
type ActiveMetadataCheckStatus = Exclude<MetadataCheckStatus, 'idle'>
type RegistrationRequestStatus = 'idle' | 'submitting' | 'processing'
type RegistrationPayload = RegistrationResponse & { detail?: string }

const draftKey = 'bcr-register-draft'

const emptyForm: RegistrationForm = {
  adapterName: '',
  repositoryLocation: '',
  licenseValue: '',
  doi: '',
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

const metadataCheckViews: Record<ActiveMetadataCheckStatus, { className: string; icon: ReactNode; text: string }> = {
  blocked: {
    className: 'bg-amber-400 text-slate-950',
    icon: <ExclamationTriangleIcon className="h-5 w-5" aria-hidden="true" />,
    text: 'CORS blocked',
  },
  checking: {
    className: 'bg-blue-100 text-blue-700',
    icon: <span className="h-2.5 w-2.5 rounded-full bg-current" aria-hidden="true" />,
    text: 'checking file',
  },
  found: {
    className: 'bg-emerald-400 text-white',
    icon: <CheckIcon className="h-5 w-5" aria-hidden="true" />,
    text: 'has croissant file',
  },
  missing: {
    className: 'bg-red-500 text-white',
    icon: <XMarkIcon className="h-5 w-5" aria-hidden="true" />,
    text: 'missing croissant file',
  },
}

/*
 * AI-Generated.
 */
function getRegistrationResultView(result: RegistrationResponse) {
  if (result.status === 'VALID') {
    return {
      iconClassName: 'bg-emerald-100 text-emerald-600',
      text: `${result.adapter_name} was stored and validated by the registry.`,
      title: 'Adapter registration successful',
    }
  }

  if (result.status === 'INVALID') {
    return {
      iconClassName: 'bg-red-100 text-red-600',
      text: 'Please fix these issues in your GitHub repository, then revalidate.',
      title: 'Sorry, your adapter is not currently valid.',
    }
  }

  return {
    iconClassName: 'bg-amber-100 text-amber-700',
    text: `${result.adapter_name} was stored. Processing feedback is shown below.`,
    title: 'Registration submitted',
  }
}

/*
 * AI-Generated.
 */
function getMetadataUrl(location: string) {
  let repositoryUrl: URL
  try {
    repositoryUrl = new URL(location)
  } catch {
    return null
  }

  const parts = repositoryUrl.pathname.split('/').filter(Boolean)
  const isGitHub = repositoryUrl.hostname === 'github.com' && parts.length >= 2
  if (!isGitHub) {
    return new URL('croissant.jsonld', location + '/').href
  }

  const isBlobUrl = parts[2] === 'blob'
  const branch = isBlobUrl && parts[3] ? parts[3] : 'main'
  const path = isBlobUrl ? parts.slice(4).join('/') : 'croissant.jsonld'

  return `https://raw.githubusercontent.com/${parts[0]}/${parts[1]}/${branch}/${path}`
}

/*
 * AI-Generated.
 */
function metadataStatusForResponse(response: Response): MetadataCheckStatus {
  if (response.ok) {
    return 'found'
  }

  return response.status === 404 ? 'missing' : 'blocked'
}

/*
 * AI-Generated.
 */
function isHttpUrl(value: string) {
  const normalizedValue = value.trim().toLowerCase()
  return normalizedValue.startsWith('http://') || normalizedValue.startsWith('https://')
}

/*
 * AI-Generated.
 */
async function readRegistrationPayload(response: Response) {
  try {
    return (await response.json()) as RegistrationPayload
  } catch (error) {
    console.warn('Could not parse registration response.', error)
    return null
  }
}

/*
 * AI-Generated.
 */
function submitButtonText(status: RegistrationRequestStatus, authUser: AuthUser | null) {
  if (status === 'submitting') {
    return 'Submitting...'
  }

  if (status === 'processing') {
    return 'Checking adapter'
  }

  return authUser ? 'Register adapter' : 'Sign in with GitHub'
}

function initialForm(): RegistrationForm {
  const savedDraft = globalThis.localStorage.getItem(draftKey)
  if (!savedDraft) {
    return emptyForm
  }

  try {
    return { ...emptyForm, ...(JSON.parse(savedDraft) as Partial<RegistrationForm>) }
  } catch {
    globalThis.localStorage.removeItem(draftKey)
    return emptyForm
  }
}


// Basically this shows errors or successfull registration
function RegistrationResultPanel({
  error,
  isProcessing,
  onRevalidate,
  result,
}: RegistrationResultPanelProps) {
  const isValid = result.status === 'VALID'
  const isInvalid = result.status === 'INVALID'
  const resultView = getRegistrationResultView(result)
  const validationErrors = result.validation_errors?.filter(Boolean) ?? []

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm md:p-10">
      <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div className="flex gap-4">
          <span
            className={`flex h-14 w-14 flex-none items-center justify-center rounded-full ${resultView.iconClassName}`}
          >
            {isValid ? (
              <CheckCircleIcon className="h-8 w-8" aria-hidden="true" />
            ) : (
              <ExclamationTriangleIcon className="h-8 w-8" aria-hidden="true" />
            )}
          </span>
          <span>
            <h2 className="text-2xl font-bold text-slate-950">
              {resultView.title}
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              {resultView.text}
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

function RegisterPage({ apiBaseUrl, authUser }: RegisterPageProps) {
  const [form, setForm] = useState<RegistrationForm>(initialForm)
  const [status, setStatus] = useState<RegistrationRequestStatus>('idle')
  const [result, setResult] = useState<RegistrationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [metadataCheckStatus, setMetadataCheckStatus] = useState<MetadataCheckStatus>('idle')
  const metadataCheckView =
    metadataCheckStatus === 'idle' ? null : metadataCheckViews[metadataCheckStatus]

  function updateField(field: keyof RegistrationForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  useEffect(() => {
    let location = form.repositoryLocation.trim()
    while (location.endsWith('/')) {
      location = location.slice(0, -1)
    }
    if (!isHttpUrl(location)) return

    const controller = new AbortController()
    const metadataUrl = getMetadataUrl(location)
    if (!metadataUrl) {
      return
    }

    void fetch(metadataUrl, { signal: controller.signal })
      .then((response) => {
        setMetadataCheckStatus(metadataStatusForResponse(response))
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setMetadataCheckStatus('blocked')
      })

    return () => controller.abort()
  }, [form.repositoryLocation])

  async function submitRegistration(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setResult(null)

    if (!authUser) {
      globalThis.localStorage.setItem(draftKey, JSON.stringify(form))
      globalThis.location.href = `${apiBaseUrl}/api/v1/auth/github/start?return_to=${encodeURIComponent('/register')}`
      return
    }

    try {
      setStatus('submitting')
      const response = await fetch(`${apiBaseUrl}/api/v1/registrations`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          adapter_name: form.adapterName,
          repository_location: form.repositoryLocation,
          license_value: form.licenseValue.trim() || undefined,
          doi: form.doi.trim() || undefined,
        }),
      })

      if (!response.ok) {
        const payload = await readRegistrationPayload(response)
        setStatus('idle')
        setError(payload?.detail ?? 'Registration failed.')
        return
      }

      const registration = (await response.json()) as RegistrationResponse
      globalThis.localStorage.removeItem(draftKey)
      setStatus('processing')

      const processResponse = await fetch(`${apiBaseUrl}/api/v1/registrations/${registration.registration_id}/process`, {
        method: 'POST',
        credentials: 'include',
      })
      const processPayload = await readRegistrationPayload(processResponse)

      setStatus('idle')
      if (!processResponse.ok) {
        setResult(registration)
        setError(processPayload?.detail ?? 'Registration was saved, but processing failed.')
        return
      }

      setResult(processPayload ?? registration)
    } catch (requestError) {
      console.error('Could not submit registration.', requestError)
      setStatus('idle')
      setError('Registration failed.')
    }
  }

  async function revalidateRegistration() {
    if (!result) return

    try {
      setStatus('processing')
      setError(null)
      const response = await fetch(`${apiBaseUrl}/api/v1/registrations/${result.registration_id}/revalidate`, {
        method: 'POST',
        credentials: 'include',
      })
      const payload = await readRegistrationPayload(response)

      setStatus('idle')
      if (!response.ok) {
        setError(payload?.detail ?? 'Revalidation failed.')
        return
      }

      setResult(payload ?? result)
    } catch (requestError) {
      console.error('Could not revalidate registration.', requestError)
      setStatus('idle')
      setError('Revalidation failed.')
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

                <label className="grid gap-3 text-sm font-semibold text-slate-950">
                  <span>Repository location*</span>
                <span className="relative block">
                  <input
                    className="h-14 w-full rounded-xl border border-slate-200 bg-slate-50 px-5 pr-48 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
                    onChange={(event) => {
                      const value = event.target.value
                      setError(null)
                      setMetadataCheckStatus(isHttpUrl(value) ? 'checking' : 'idle')
                      updateField('repositoryLocation', value)
                    }}
                    placeholder="https://github.com/example/clinical-visit-adapter"
                    required
                    type="url"
                    value={form.repositoryLocation}
                  />
                  {metadataCheckView ? (
                    <span
                      aria-live="polite"
                      className={`pointer-events-none absolute right-1.5 top-1/2 inline-flex h-12 -translate-y-1/2 items-center gap-2 rounded-2xl px-4 text-sm font-medium ${metadataCheckView.className}`}
                    >
                      {metadataCheckView.icon}
                      {metadataCheckView.text}
                    </span>
                  ) : null}
                </span>
                </label>

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
                  onChange={(event) => updateField('doi', event.target.value)}
                  placeholder="10.5281/zenodo.1234567"
                  type="text"
                  value={form.doi}
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
                {submitButtonText(status, authUser)}
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
