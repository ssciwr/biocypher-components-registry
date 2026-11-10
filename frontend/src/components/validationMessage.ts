export type FormattedValidatorMessage = Readonly<{
  alternatives: string[]
  prefix: string
  suffix: string
}>

const urlPattern = /https?:\/\/[^\s]+/g

/**
 * Split validator messages containing URI alternatives without paraphrasing them.
 * Unknown messages deliberately remain untouched.
 */
export function formatValidatorMessage(message: string): FormattedValidatorMessage | null {
  const matches = [...message.matchAll(urlPattern)]
  if (matches.length < 2 || matches.some((match) => match.index === undefined)) return null

  const urls: string[] = []
  let finalEnd = 0
  for (const match of matches) {
    const start = match.index ?? 0
    const raw = match[0]
    const isFinal = match === matches.at(-1)
    const url = isFinal ? raw.replace(/[.,;:]$/, '') : raw
    const end = start + raw.length

    if (urls.length) {
      const connector = message.slice(finalEnd, start).trim()
      if (connector !== 'or') return null
    }
    urls.push(url)
    finalEnd = end - (raw.length - url.length)
  }

  const firstIndex = matches[0].index ?? 0
  return {
    prefix: message.slice(0, firstIndex).trimEnd(),
    alternatives: urls,
    suffix: message.slice(finalEnd),
  }
}
