import { useEffect, useState } from 'react'
import { BookOpenIcon } from '@heroicons/react/24/outline'

type CitationEndorsementProps = Readonly<{
  doi: string | null
}>

type CrossrefWork = {
  count: number
  title: string
  authors: string[]
}

type CitationWork = CrossrefWork & {
  doi: string
}

const crossrefWorksBaseUrl = 'https://api.crossref.org/works' // hardcoded as only used in this one place. invalid DOIs mean the citation information will not be rendered

function CitationEndorsement({ doi }: CitationEndorsementProps) {
  const doiValue = doi?.trim() || ''
  const [citation, setCitation] = useState<false | null | CitationWork>(null)

  useEffect(() => {
    if (!doiValue) return

    void fetchCrossrefWork(doiValue)
      .then((work) => {
        setCitation(work ? { doi: doiValue, ...work } : false)
      })
      .catch(() => {
        setCitation(false) // if invalid or missing parts
      })
  }, [doiValue])

  if (!doiValue || citation === false) return null

  const activeCitation = citation?.doi === doiValue ? citation : null

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-start gap-3">
        <BookOpenIcon className="mt-0.5 h-5 w-5 flex-none text-slate-500" aria-hidden="true" />
        <div className="min-w-0">
          {!activeCitation ? (
            <p className="text-sm text-slate-600">Loading citation data...</p>
          ) : (
            <>
              <p className="text-sm font-semibold uppercase tracking-normal text-slate-500">Cited by</p>
              <p className="mt-1 text-3xl font-bold text-slate-950">{activeCitation.count.toLocaleString()}</p>
              <p className="mt-4 text-sm font-semibold leading-5 text-slate-950">{activeCitation.title}</p>
              <p className="mt-3 text-sm leading-5 text-slate-600">{activeCitation.authors.join(', ')}</p>
            </>
          )}
          <a className="mt-4 block break-all text-sm text-blue-600 hover:text-blue-700" href={`https://doi.org/${doiValue}`} rel="noreferrer" target="_blank">
            {doiValue}
          </a>
        </div>
      </div>
    </div>
  )
}

async function fetchCrossrefWork(doi: string): Promise<CrossrefWork | false> {
  const response = await fetch(`${crossrefWorksBaseUrl}/${encodeURIComponent(doi)}`)
  if (!response.ok) return false

  const payload = (await response.json()) as { message?: Record<string, unknown> }
  const message = payload.message
  if (!message) return false

  const count = message['is-referenced-by-count']
  const title = message.title ? String(message.title).trim() : false
  const authors = Array.isArray(message.author)
    ? (message.author as Array<{ given?: string; family?: string; name?: string } | null>)
        .map((author) => (
          [author?.given, author?.family].filter(Boolean).join(' ') || String(author?.name || '')
        ).trim())
        .filter((name) => name.length > 1)
    : []

  if (typeof count !== 'number' || !Number.isFinite(count) || !title || authors.length === 0) return false

  return { count, title, authors }
}


export default CitationEndorsement
