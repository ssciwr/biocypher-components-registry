import { useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRightIcon, PlusIcon } from '@heroicons/react/24/outline'
import type { AuthUser } from '../components/AppHeader'

type RegisterPageProps = {
  apiBaseUrl: string
  authUser: AuthUser | null
}

type RegistrationForm = {
  adapterName: string
  repositoryLocation: string
  licenseValue: string
  doi: string
}

type RegistrationResponse = {
  registration_id: string
  adapter_name: string
  submitted_by_github_login: string | null
}

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

function RegisterPage({ apiBaseUrl, authUser }: RegisterPageProps) {
  const [form, setForm] = useState<RegistrationForm>(initialForm)
  const [status, setStatus] = useState<'idle' | 'submitting' | 'submitted'>('idle')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  function updateField(field: keyof RegistrationForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function submitRegistration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setMessage(null)

    if (!authUser) {
      window.localStorage.setItem(draftKey, JSON.stringify(form))
      window.location.href = `${apiBaseUrl}/api/v1/auth/github/start?return_to=${encodeURIComponent('/register')}`
      return
    }

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
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null
      setStatus('idle')
      setError(payload?.detail ?? 'Registration failed.')
      return
    }

    const registration = (await response.json()) as RegistrationResponse
    window.localStorage.removeItem(draftKey)
    setStatus('submitted')
    setMessage(`Registration submitted for ${registration.adapter_name}.`)
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
                <input
                  className="h-14 rounded-xl border border-slate-200 bg-slate-50 px-5 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white"
                  onChange={(event) => updateField('repositoryLocation', event.target.value)}
                  placeholder="https://github.com/example/clinical-visit-adapter"
                  required
                  type="url"
                  value={form.repositoryLocation}
                />
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
                disabled={status === 'submitting'}
                type="submit"
              >
                {authUser ? 'Register adapter' : 'Sign in with GitHub'}
                {authUser ? (
                  <PlusIcon className="h-5 w-5" aria-hidden="true" />
                ) : (
                  <ArrowRightIcon className="h-5 w-5" aria-hidden="true" />
                )}
              </button>
            </div>

            {message ? (
              <p className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                {message}
              </p>
            ) : null}
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
      </div>
    </section>
  )
}

export default RegisterPage
