import { useEffect, useState } from 'react'
import { BookOpenIcon } from '@heroicons/react/24/outline'
import { fetchCrossrefWork, type CrossrefWork } from '../api/crossref'

type CitationEndorsementProps = Readonly<{
  doi: string | null
}>

type CitationWork = CrossrefWork & {
  count: number
  doi: string
  title: string
}

function CitationEndorsement({ doi }: CitationEndorsementProps) {
  const doiValue = doi?.trim() || ''
  const [citation, setCitation] = useState<false | null | CitationWork>(null)

  useEffect(() => {
    if (!doiValue) return

    void fetchCrossrefWork(doiValue)
      .then((work) => {
        if (!work || typeof work.count !== 'number' || !work.title || work.authors.length === 0) {
          setCitation(false)
          return
        }
        setCitation({ authors: work.authors, count: work.count, doi: doiValue, title: work.title })
      })
      .catch((error: unknown) => {
        console.error('Could not load Crossref citation data.', error)
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

export default CitationEndorsement
