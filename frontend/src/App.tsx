import { useEffect, useState } from 'react'
import {
  ArrowRightIcon,
  CloudArrowUpIcon,
  CommandLineIcon,
  DocumentPlusIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline'
import AppHeader from './components/AppHeader'
import type { AuthUser } from './components/AppHeader'
import RegisterPage from './pages/RegisterPage'
import AdaptersPage from './pages/AdaptersPage'
import { getMeApiV1AuthMeGet, logoutApiV1AuthLogoutPost } from './api/client'
import { client } from './api/client/client.gen'

const actionCards = [
  {
    label: 'Explore adapters',
    icon: MagnifyingGlassIcon,
    text: 'Search reusable components and inspect adapter metadata like data sources.',
    cta: 'Browse adapters',
    href: '/adapters',
    tone: 'bg-cyan-100 text-cyan-700',
  },
  {
    label: 'Create',
    icon: DocumentPlusIcon,
    text: 'Create BioCypher adapters and metadata.',
    cta: 'Start creating',
    href: '/register',
    featured: true,
    tone: 'bg-white/20 text-white',
  },
  {
    label: 'Register adapter',
    icon: CloudArrowUpIcon,
    text: 'Submit your adapter repository to our registry, so others can use it.',
    cta: 'Register now',
    href: '/register',
    tone: 'bg-blue-100 text-blue-700',
  },
]

const popularAdapters = ['Open Targets', 'OmniPath', 'Collectri adapter']

const authUserKey = 'bcr-auth-user' // does not really matter, just needs to be hardcoded between hte save/read.

// To persist if they reopen the browser, not really needed but I found it improves developer experience too as otherwise
// each time you edit code (e.g. a small AI agent change), the reloaded codebase means you would get logged out before
function cacheAuthUser(user: AuthUser | null) {
  if (user) {
    window.localStorage.setItem(authUserKey, JSON.stringify(user))
    return
  }
  window.localStorage.removeItem(authUserKey)
}


function readCachedAuthUser(): AuthUser | null {
  const savedUser = window.localStorage.getItem(authUserKey)
  if (!savedUser) {
    return null
  }

  try {
    const user = JSON.parse(savedUser) as Partial<AuthUser>
    return typeof user.github_login === 'string' ? { github_login: user.github_login } : null
  } catch {
    window.localStorage.removeItem(authUserKey)
    return null
  }
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
client.setConfig({ baseUrl: apiBaseUrl, credentials: 'include' }) // for openapi-ts

function App() {
  const [authUser, setAuthUser] = useState<AuthUser | null>(readCachedAuthUser)
  const [authError, setAuthError] = useState<string | null>(null)
  const [pathname, setPathname] = useState(window.location.pathname)

  useEffect(() => {
    let ignore = false

    void getMeApiV1AuthMeGet()
      .then((result) => {
        if (ignore) return

        if (result.data) {
          setAuthUser(result.data)
          cacheAuthUser(result.data)
          setAuthError(null)
          return
        }

        if (result.response?.status === 401) {
          setAuthUser(null)
          cacheAuthUser(null)
        }
        setAuthError(null)
      })
      .catch(() => {
        if (!ignore) setAuthError(null)
      })

    return () => {
      ignore = true
    }
  }, [])

  useEffect(() => {
    const updatePathname = () => setPathname(window.location.pathname)
    window.addEventListener('popstate', updatePathname)
    return () => window.removeEventListener('popstate', updatePathname)
  }, [])


  async function logOut() {
    try {
      const result = await logoutApiV1AuthLogoutPost()
      const logoutError = result.error as unknown

      if (logoutError) {
        setAuthError(typeof logoutError === 'string' && logoutError ? logoutError : (logoutError as { details?: string; detail?: string } | undefined)?.details || (logoutError as { details?: string; detail?: string } | undefined)?.detail || 'Sign out failed.')
        return
      }

      setAuthUser(null)
      cacheAuthUser(null)
      setAuthError(null)
    } catch (error) {
      setAuthError(typeof error === 'string' && error ? error : (error as { details?: string; detail?: string } | undefined)?.details || (error as { details?: string; detail?: string } | undefined)?.detail || 'Sign out failed.')
    }
  }

  const adapterId = pathname.match(/^\/adapters\/([^/]+)$/)?.[1]

  return (
    <main className="min-h-screen bg-slate-100 text-slate-950">
      <AppHeader authUser={authUser} onLogout={logOut} />
      {authError ? (
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-3 text-sm text-amber-800" role="alert">
          {authError}
        </div>
      ) : null}
      {pathname === '/register' ? (
        <RegisterPage authUser={authUser} />
      ) : pathname === '/adapters' || adapterId ? (
        <AdaptersPage adapterId={adapterId} />
      ) : (
        <HomePage />
      )}
      <Footer />
    </main>
  )
}

function HomePage() {
  return (
    <>
      <section className="bg-blue-50">
        <div className="mx-auto max-w-5xl px-6 pb-14 pt-6 text-center md:pb-20">
          <div className="mx-auto inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-xs text-blue-600">
            <span className="h-2 w-2 rounded-full bg-lime-500" aria-hidden="true" />
            Discover adapters, generate metadata, and register components
          </div>
          <h1 className="mx-auto mt-7 max-w-3xl text-4xl font-bold leading-tight tracking-normal text-slate-950 md:text-5xl">
            Find BioCypher components<br /> for your research
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-base text-slate-600 md:text-lg">
            Search adapters, create Croissant metadata, and submit your adapter repository to us
          </p>

          <label className="mx-auto mt-14 flex max-w-3xl items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left shadow-sm">
            <MagnifyingGlassIcon className="h-5 w-5 flex-none text-slate-300" aria-hidden="true" />
            <input
              aria-label="Search adapters"
              className="w-full bg-transparent text-base text-slate-700 outline-none placeholder:text-slate-500"
              placeholder="Search adapters..."
              type="search"
            />
          </label>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-3 text-xs text-slate-600">
            <span>Popular:</span>
            {popularAdapters.map((adapter) => (
              <a
                className="min-w-32 rounded-lg border border-slate-200 bg-white px-5 py-2 text-slate-800 hover:border-blue-200 hover:text-blue-600"
                href={`/adapters?query=${encodeURIComponent(adapter)}`}
                key={adapter}
              >
                {adapter}
              </a>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-slate-50">
        <div className="mx-auto max-w-6xl px-6 py-10 md:py-12">
          <div className="grid gap-8 md:grid-cols-3">
            {actionCards.map((card) => {
              const Icon = card.icon

              return (
                <a
                  className={`rounded-2xl border p-7 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${card.featured ? 'border-blue-600 bg-blue-600 text-white shadow-blue-100 hover:bg-blue-700' : 'border-slate-200 bg-white hover:border-blue-200'}`}
                  href={card.href}
                  key={card.label}
                >
                  <span
                    className={`inline-flex h-10 w-10 items-center justify-center rounded-xl ${card.tone}`}
                  >
                    <Icon className="h-6 w-6" aria-hidden="true" />
                  </span>
                  <h2 className={`mt-4 text-xl font-bold ${card.featured ? 'text-white' : 'text-slate-950'}`}>{card.label}</h2>
                  <p className={`mt-3 min-h-12 text-sm leading-5 ${card.featured ? 'text-blue-50' : 'text-slate-600'}`}>{card.text}</p>
                  <span className={`mt-8 inline-flex items-center gap-1 text-sm font-medium ${card.featured ? 'text-white' : 'text-blue-600'}`}>
                    {card.cta}
                    <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />
                  </span>
                </a>
              )
            })}
          </div>

          <a
            className="mt-8 flex flex-col gap-5 rounded-2xl border border-blue-100 bg-white p-8 text-left shadow-sm transition hover:border-blue-200 hover:shadow-md md:flex-row md:items-center"
            href="/adapters"
          >
            <span className="inline-flex h-12 w-12 flex-none items-center justify-center rounded-xl bg-blue-600 text-white">
              <CommandLineIcon className="h-7 w-7" aria-hidden="true" />
            </span>
            <span>
              <span className="block text-2xl font-bold text-slate-950">
                Move into better biology research
              </span>
              <span className="mt-2 block text-base text-slate-700">
                Try our MCP workspace to build adapters for datasets you want to work with, using
                your LLM.
              </span>
              <span className="mt-2 block text-sm leading-6 text-slate-500">
                Our MCP server guides the workflow and provides examples, helping your research code
                be written more accurately and thoroughly.
              </span>
            </span>
          </a>
        </div>
      </section>
    </>
  )
}

function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-7 text-xs text-slate-500">
        <a
          className="hover:text-blue-600"
          href="https://github.com/ssciwr/biocypher-components-registry"
          rel="noreferrer"
          target="_blank"
        >
          GitHub
        </a>
        <span>BioCypher Components Registry</span>
      </div>
    </footer>
  )
}

export default App
