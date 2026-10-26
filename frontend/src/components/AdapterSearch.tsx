import { useEffect, useState, type ReactNode } from 'react'
import { ArrowPathIcon, ExclamationTriangleIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import {
  listLatestAdaptersApiV1AdaptersLatestGet,
  searchAdaptersApiV1AdaptersSearchGet,
  type AdapterLatestItemResponse,
} from '../api/client'
import MaintainerAvatar from './MaintainerAvatar'

function AdapterSearch({ showLatest = true, children }: Readonly<{ showLatest?: boolean; children?: ReactNode }>) {
  const [adapters, setAdapters] = useState<AdapterLatestItemResponse[] | null>(null)
  const [query, setQuery] = useState(() => showLatest ? new URLSearchParams(window.location.search).get('query') ?? '' : '')
  const [loadError, setLoadError] = useState(false)
  const showResults = showLatest || Boolean(query.trim())

  useEffect(() => {
    let ignore = false
    const searchTerm = query.trim()
    if (!showLatest && !searchTerm) return

    const adapterRequest = searchTerm
      ? searchAdaptersApiV1AdaptersSearchGet({
          query: { query: searchTerm },
        })
      : listLatestAdaptersApiV1AdaptersLatestGet()

    void adapterRequest
      .then((result) => {
        if (ignore) return

        const adapterListError = result.error as unknown
        if (adapterListError || !result.data) {
          setAdapters([])
          setLoadError(true)
          return
        }

        setAdapters(result.data.items)
        setLoadError(false)
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
  }, [query, showLatest])

  return (
    <>
      <label className={`mx-auto flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left shadow-sm ${showLatest ? 'mt-8 max-w-2xl' : 'mt-14 max-w-3xl'}`}>
        <MagnifyingGlassIcon className="h-5 w-5 flex-none text-slate-300" aria-hidden="true" />
        <input
          aria-label="Search adapters"
          className="w-full bg-transparent text-base text-slate-700 outline-none placeholder:text-slate-500"
          onChange={(event) => {
            setQuery(event.target.value)
            setAdapters(null)
            setLoadError(false)
          }}
          placeholder="Search adapters..."
          type="search"
          value={query}
        />
      </label>

      {children}

      {showResults && loadError ? (
        <div className="mx-auto mt-8 flex max-w-2xl items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-left text-red-700" role="alert">
          <ExclamationTriangleIcon className="h-5 w-5 flex-none" aria-hidden="true" />
          <span>Unable to load adapters right now...</span>
        </div>
      ) : null}

      {showResults ? (
        <div className="mt-14 grid gap-8 text-left md:grid-cols-2 xl:grid-cols-4">
          {adapters === null ? (
            <div className="col-span-full flex justify-center text-slate-500" role="status">
              <ArrowPathIcon className="h-6 w-6 animate-spin" aria-hidden="true" />
              <span className="sr-only">Searching adapters...</span>
            </div>
          ) : null}
          {!loadError && adapters?.length === 0 ? (
            <p className="col-span-full text-center text-slate-500" role="status">No adapters found</p>
          ) : null}
          {adapters?.map((adapter) => (
            <article
              className="flex min-h-72 flex-col rounded-lg border border-slate-200 bg-white p-6 shadow-sm transition hover:border-blue-200 hover:shadow-md"
              key={adapter.adapter_id}
            >
              <a className="block" href={`/adapters/${adapter.adapter_id}`}>
                <h2 className="text-xl font-bold text-slate-950">{adapter.adapter_name}</h2>
                <p className="mt-5 line-clamp-4 text-sm leading-5 text-slate-800">
                  {adapter.description ?? 'No adapter description has been submitted yet.'}
                </p>
              </a>
              <div className="mt-5 flex flex-wrap gap-2">
                {(adapter.keywords ?? []).slice(0, 3).map((keyword) => (
                  <span className="rounded-full bg-slate-200/70 px-3 py-1 text-xs font-medium text-slate-700" key={keyword}>
                    {keyword}
                  </span>
                ))}
              </div>
              <div className="mt-auto flex items-center justify-between gap-2 pt-6">
                <MaintainerAvatar maintainer={adapter.maintainer} />
                <span className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-600">
                  <span aria-hidden="true">👍</span>
                  <span>{adapter.endorsement_count ?? 0}</span>
                </span>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </>
  )
}

export default AdapterSearch
