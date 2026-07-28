export type CrossrefWork = Readonly<{
  authors: string[]
  count: number | null
  title: string | null
}>

const crossrefWorksBaseUrl = 'https://api.crossref.org/works'

/*
 * AI-Generated.
 */
export async function fetchCrossrefWork(doi: string): Promise<CrossrefWork | false> {
  const response = await fetch(`${crossrefWorksBaseUrl}/${encodeURIComponent(doi)}`) // NOSONAR: the DOI is encoded and appended to a configured Crossref works endpoint; bad user input can only query Crossref for a missing work.
  if (!response.ok) return false

  const payload = (await response.json()) as { message?: Record<string, unknown> }
  const message = payload.message
  if (!message) return false

  const countValue = message['is-referenced-by-count']
  const titleValue = message.title
  let title = ''
  if (Array.isArray(titleValue)) {
    title = String(titleValue[0] || '').trim()
  } else if (typeof titleValue === 'string') {
    title = titleValue.trim()
  }
  const authors = Array.isArray(message.author)
    ? (message.author as Array<{ given?: string; family?: string; name?: string } | null>)
        .map((author) => (
          [author?.given, author?.family].filter(Boolean).join(' ') || String(author?.name || '')
        ).trim())
        .filter((name) => name.length > 1)
    : []

  return {
    authors,
    count: typeof countValue === 'number' && Number.isFinite(countValue) ? countValue : null,
    title: title || null,
  }
}
