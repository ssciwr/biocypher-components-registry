import { useEffect, useState } from 'react'
import {
  CircleStackIcon,
  ExclamationTriangleIcon,
  FlagIcon,
  MagnifyingGlassIcon,
  RocketLaunchIcon,
  StarIcon,
} from '@heroicons/react/24/outline'
import GenericModal from '../components/GenericModal'
import LinkToModal from '../components/LinkToModal'

type Maintainer = {
  github_login: string
  avatar_url: string
}

type DataSource = {
  name: string
  description: string | null
  version: string | null
  license: string | null
  url: string | null
  column_count: number | null
}

type LatestAdapter = {
  adapter_id: string
  adapter_name: string
  latest_version: string
  description: string | null
  repository_location: string | null
  keywords: string[]
  maintainers: Maintainer[]
  endorsement_count: number
  endorsed_by_current_user: boolean
  updated_at: string
}

type AdapterDetail = LatestAdapter & {
  license_value: string | null
  data_sources: DataSource[]
}

type AdapterEndorsement = {
  adapter_id: string
  endorsement_count: number
  endorsed_by_current_user: boolean
}

type AdaptersPageProps = {
  adapterId?: string
  apiBaseUrl: string
}

function AdaptersPage({ adapterId, apiBaseUrl }: AdaptersPageProps) {
  return adapterId ? (
    <AdapterDetailView adapterId={adapterId} apiBaseUrl={apiBaseUrl} />
  ) : (
    <AdapterListView apiBaseUrl={apiBaseUrl} />
  )
}

function AdapterListView({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [adapters, setAdapters] = useState<LatestAdapter[]>([])
  const [query, setQuery] = useState('')
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    let ignore = false
    fetch(`${apiBaseUrl}/api/v1/adapters/latest?limit=10`, { credentials: 'include' })
      .then((response) => {
        if (!response.ok) throw new Error('Adapter API unavailable')
        return response.json()
      })
      .then((payload: { items?: LatestAdapter[] }) => {
        if (!ignore) {
          setAdapters(payload.items ?? [])
          setLoadError(false)
        }
      })
      .catch(() => {
        if (!ignore) {
          setAdapters([])
          setLoadError(true)
        }
      })
    return () => {
      ignore = true
    }
  }, [apiBaseUrl])

  const filteredAdapters = adapters.filter((adapter) =>
    `${adapter.adapter_name} ${adapter.description ?? ''} ${adapter.keywords.join(' ')}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  )


  return (
    <section className="bg-slate-100">
      <div className="mx-auto max-w-7xl px-6 py-16 md:py-20">
        <h1 className="text-center text-4xl font-semibold tracking-normal text-slate-950 md:text-5xl">
          BioCypher Adapter Repository
        </h1>
        <label className="mx-auto mt-8 flex max-w-2xl items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <MagnifyingGlassIcon className="h-5 w-5 flex-none text-slate-300" aria-hidden="true" />
          <input
            aria-label="Search adapters"
            className="w-full bg-transparent text-base text-slate-700 outline-none placeholder:text-slate-500"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search adapters..."
            type="search"
            value={query}
          />
        </label>

        {loadError ? (
          <div className="mx-auto mt-8 flex max-w-2xl items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700" role="alert">
            <ExclamationTriangleIcon className="h-5 w-5 flex-none" aria-hidden="true" />
            <span>Unable to load adapters right now...</span>
          </div>
        ) : null}

        <div className="mt-14 grid gap-8 md:grid-cols-2 xl:grid-cols-4">
          {filteredAdapters.map((adapter) => (
            <article
              className="flex min-h-72 flex-col rounded-lg border border-slate-200 bg-white p-6 shadow-sm transition hover:border-blue-200 hover:shadow-md"
              key={adapter.adapter_id}
            >
              <a className="block" href={`/adapters/${adapter.adapter_id}`}>
                <h2 className="text-xl font-bold text-slate-950">{adapter.adapter_name}</h2>
                <p className="mt-2 text-sm text-slate-500">v{adapter.latest_version}</p>
                <p className="mt-5 line-clamp-4 text-sm leading-5 text-slate-800">
                  {adapter.description ?? 'No adapter description has been submitted yet.'}
                </p>
              </a>
              <div className="mt-5 flex flex-wrap gap-2">
                {adapter.keywords.slice(0, 3).map((keyword) => (
                  <span className="rounded-full bg-slate-200/70 px-3 py-1 text-xs font-medium text-slate-700" key={keyword}>
                    {keyword}
                  </span>
                ))}
              </div>
              <div className="mt-auto flex items-center justify-between gap-2 pt-6">
                <AvatarGroup maintainers={adapter.maintainers} />
                <span className="inline-flex items-center gap-1 text-sm text-slate-500">
                  <span aria-hidden="true">👍</span>
                  <span>{adapter.endorsement_count ?? 0}</span>
                </span>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

function AdapterDetailView({ adapterId, apiBaseUrl }: { adapterId: string; apiBaseUrl: string }) {
  const [adapter, setAdapter] = useState<AdapterDetail | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [isEndorsing, setIsEndorsing] = useState(false)
  const [endorsementError, setEndorsementError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false
    fetch(`${apiBaseUrl}/api/v1/adapters/${adapterId}`, { credentials: 'include' })
      .then((response) => {
        if (!response.ok) throw new Error('Adapter detail API unavailable')
        return response.json()
      })
      .then((payload: AdapterDetail) => {
        if (!ignore) {
          setAdapter(payload)
          setLoadError(false)
        }
      })
      .catch(() => {
        if (!ignore) {
          setAdapter(null)
          setLoadError(true)
        }
      })
    return () => {
      ignore = true
    }
  }, [adapterId, apiBaseUrl])


  /*
   * AI-Generated.
   */
  async function endorseCurrentAdapter() {
    setIsEndorsing(true)
    setEndorsementError(null)
    try {
      const endorsement = await endorseAdapter(apiBaseUrl, adapterId)
      if (!endorsement) return
      setAdapter((currentAdapter) => currentAdapter
        ? {
            ...currentAdapter,
            endorsement_count: endorsement.endorsement_count,
            endorsed_by_current_user: endorsement.endorsed_by_current_user,
          }
        : currentAdapter,
      )
    } catch {
      setEndorsementError('Could not endorse this adapter. Please try again.')
    } finally {
      setIsEndorsing(false)
    }
  }

  if (loadError) {
    return (
      <section className="bg-slate-100 px-6 py-20">
        <div className="mx-auto flex max-w-2xl items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700" role="alert">
          <ExclamationTriangleIcon className="h-5 w-5 flex-none" aria-hidden="true" />
          <span>Error trying to load adapter...</span>
        </div>
      </section>
    )
  }

  if (!adapter) {
    return <section className="px-6 py-20 text-center text-slate-500">Loading adapter...</section>
  }

  const adapterRepositoryHref = githubRepositoryUrl(adapter.repository_location) ?? adapter.repository_location ?? '#'

  return (
    <section className="bg-slate-100">
      <div className="mx-auto grid max-w-6xl items-start gap-6 px-4 py-10 sm:px-6 md:py-14 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="grid min-w-0 gap-6">
          <section className="min-w-0 rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
            <p className="text-sm text-slate-500">{repoLabel(adapter.repository_location)}</p>
            <h1 className="mt-2 text-2xl font-bold tracking-normal text-slate-950 sm:text-3xl">{adapter.adapter_name}</h1>
            <div className="mt-5 rounded-lg border border-slate-200 p-4 sm:p-6">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-base font-bold text-slate-950">Overview</h2>
                {adapter.keywords.slice(0, 4).map((keyword) => (
                  <span className="rounded-full bg-slate-200/70 px-3 py-1 text-xs font-medium text-slate-700" key={keyword}>
                    {keyword}
                  </span>
                ))}
              </div>
              <p className="mt-4 text-base leading-6 text-slate-800">
                {adapter.description ?? 'No adapter description has been submitted yet.'}
              </p>
              <h3 className="mt-7 flex items-center gap-2 text-sm font-bold text-slate-950">
                <RocketLaunchIcon className="h-5 w-5 text-blue-600" aria-hidden="true" />
                Quick Example
              </h3>
              <pre className="mt-4 max-w-full overflow-x-auto rounded-lg bg-black p-4 text-xs leading-5 text-white sm:p-5">
{`from biocypher import BioCypher

bc = BioCypher()
bc.add_adapter(${JSON.stringify(adapter.adapter_name)})
bc.run()`}
              </pre>
            </div>
          </section>

          <section className="min-w-0 rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
            <h2 className="flex items-center gap-2 text-2xl font-bold text-slate-950">
              <CircleStackIcon className="h-6 w-6" aria-hidden="true" />
              Data Sources
            </h2>
            <div className="mt-5 divide-y divide-slate-200 border border-slate-200">
              {(adapter.data_sources.length ? adapter.data_sources : [{ name: 'No data sources listed', description: null, version: null, license: null, url: null, column_count: null }]).map((source) => (
                <div className="p-4" key={source.name}>
                  <div className="flex items-center justify-between gap-4">
                    <h3 className="text-base font-semibold text-slate-950">{source.name}</h3>
                    {source.column_count ? <ColumnModal source={source} /> : null}
                  </div>
                  {source.description ? <p className="mt-3 text-sm leading-5 text-slate-700">{source.description}</p> : null}
                  <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-700">
                    {source.license ? <span>License: {source.license}</span> : null}
                    {source.version ? <span>Version: {source.version}</span> : null}
                    {source.url ? <a className="text-blue-600 hover:text-blue-700" href={source.url}>URL: {source.url}</a> : null}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="grid min-w-0 content-start gap-6">
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
            <a
              className="inline-flex min-h-12 w-full cursor-pointer items-center justify-center gap-3 rounded-lg bg-blue-600 px-5 py-3 text-base font-semibold text-white hover:bg-blue-700 sm:min-h-14 sm:text-lg"
              href={adapterRepositoryHref}
              rel="noreferrer"
              target="_blank"
            >
              <RocketLaunchIcon className="h-7 w-7" aria-hidden="true" />
              Use this Adapter
            </a>
            <div className="mt-7 flex items-start gap-3 text-sm text-slate-700">
              <StarIcon className="h-5 w-5 text-amber-400" aria-hidden="true" />
              <a className="break-all text-blue-600 hover:text-blue-700" href={adapterRepositoryHref} rel="noreferrer" target="_blank">
                {adapterRepositoryHref === '#' ? 'Repository URL not available' : adapterRepositoryHref}
              </a>
            </div>
            <button
              aria-label={`Endorse ${adapter.adapter_name}`}
              className="mt-5 inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-slate-600 hover:bg-slate-100 hover:text-blue-600 disabled:cursor-default disabled:opacity-70"
              disabled={isEndorsing || adapter.endorsed_by_current_user}
              onClick={() => void endorseCurrentAdapter()}
              type="button"
            >
              <span aria-hidden="true">👍</span>
              <span>{adapter.endorsement_count ?? 0}</span>
            </button>
            {endorsementError ? (
              <p className="mt-2 text-sm text-red-700" role="alert">{endorsementError}</p>
            ) : null}
            <div className="mt-6 flex flex-wrap gap-3 text-xs">
              {adapter.license_value ? <span className="rounded-full bg-emerald-100 px-3 py-1.5 font-medium text-emerald-800">{adapter.license_value}</span> : null}
              <span className="rounded-full bg-slate-200 px-3 py-1.5 font-medium text-slate-700">v{adapter.latest_version}</span>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-slate-950">Maintainer</h2>
            <div className="mt-3 rounded-lg border border-slate-200 bg-white p-5">
              <AvatarGroup maintainers={adapter.maintainers} showNames />
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-slate-950">Cite</h2>
            <div className="mt-3 rounded-lg border border-slate-200 bg-white p-5">
              <p className="text-sm text-slate-700">Cite this adapter via its .cff file</p>
              <a className="mt-4 inline-flex cursor-pointer rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white" href={cffUrl(adapter.repository_location)}>
                Cite
              </a>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-slate-950">Report Issue</h2>
            <div className="mt-3 rounded-lg border border-slate-200 bg-white p-5">
              <p className="text-sm text-slate-700">Report any issue related to this adapter.</p>
              <LinkToModal modal={<GenericModal title={`What is your concern about ${adapter.adapter_name}?`} content={<ReportLinks repositoryLocation={adapter.repository_location} />} />}>
                <span className="inline-flex items-center gap-2 text-sm font-semibold">
                  <FlagIcon className="h-4 w-4" aria-hidden="true" />
                  Report
                </span>
              </LinkToModal>
            </div>
          </section>
        </aside>
      </div>
    </section>
  )
}

function AvatarGroup({ maintainers, showNames = false }: { maintainers: Maintainer[]; showNames?: boolean }) {
  if (!maintainers.length) return <span className="text-sm text-slate-500">No GitHub maintainer recorded</span>
  return (
    <div className="flex flex-wrap items-center gap-4">
      {maintainers.map((maintainer) => (
        <span className="flex items-center gap-3" key={maintainer.github_login}>
          <img alt={maintainer.github_login} className="h-10 w-10 rounded-full border border-slate-200" src={maintainer.avatar_url} />
          {showNames ? (
            <span>
              <span className="block text-sm font-medium text-slate-950">{maintainer.github_login}</span>
              <span className="block text-xs text-slate-500">@{maintainer.github_login}</span>
            </span>
          ) : null}
        </span>
      ))}
    </div>
  )
}

function ColumnModal({ source }: { source: DataSource }) {
  // todo: show real field/column metadata when backend exposes parsed recordSet fields.
  return (
    <LinkToModal modal={<GenericModal title={`Data Source "${source.name}" - ${source.column_count} Columns`} content={<div className="text-sm text-slate-700">Column metadata is not exposed by the adapter API yet.</div>} />}>
      {source.column_count} Columns
    </LinkToModal>
  )
}

function ReportLinks({ repositoryLocation }: { repositoryLocation: string | null }) {
  return (
    <div className="grid gap-4">
      <a className="cursor-pointer rounded-lg bg-blue-600 px-5 py-4 text-center text-base font-semibold text-white" href={issuesUrl(repositoryLocation)} rel="noreferrer" target="_blank">
        Adapter is Broken/Incorrect
      </a>
      <a className="cursor-pointer rounded-lg bg-blue-600 px-5 py-4 text-center text-base font-semibold text-white" href="https://github.com/orgs/biocypher/projects/3" rel="noreferrer" target="_blank">
        Content is inappropriate/dangerous
      </a>
    </div>
  )
}

async function endorseAdapter(apiBaseUrl: string, adapterId: string): Promise<AdapterEndorsement | null> {
  const response = await fetch(`${apiBaseUrl}/api/v1/adapters/${adapterId}/endorse`, {
    method: 'POST',
    credentials: 'include',
  })
  if (response.status === 401) {
    window.location.href = `${apiBaseUrl}/api/v1/auth/github/start?return_to=${encodeURIComponent(window.location.pathname)}`
    return null
  }
  if (!response.ok) throw new Error('Adapter endorsement API unavailable')
  return response.json()
}

function repoLabel(repositoryLocation: string | null) {
  const repositoryUrl = githubRepositoryUrl(repositoryLocation)
  return repositoryUrl?.replace('https://github.com/', '') ?? 'Repository not available'
}

function issuesUrl(repositoryLocation: string | null) {
  const repositoryUrl = githubRepositoryUrl(repositoryLocation)
  return repositoryUrl ? `${repositoryUrl}/issues` : 'https://github.com/biocypher'
}

function cffUrl(repositoryLocation: string | null) {
  const repositoryUrl = githubRepositoryUrl(repositoryLocation)
  return repositoryUrl ? `${repositoryUrl}/blob/main/CITATION.cff` : '#'
}

function githubRepositoryUrl(repositoryLocation: string | null) {
  if (!repositoryLocation) return null
  const normalized = repositoryLocation.startsWith('github.com/')
    ? `https://${repositoryLocation}`
    : repositoryLocation

  try {
    const url = new URL(normalized)
    const [owner, repo] = url.pathname.split('/').filter(Boolean)
    return url.hostname === 'github.com' && owner && repo
      ? `https://github.com/${owner}/${repo}`
      : null
  } catch {
    return null
  }
}

export default AdaptersPage
