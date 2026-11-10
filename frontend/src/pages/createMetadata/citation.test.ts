import { describe, expect, it } from 'vitest'
import { citationTextFromBibtexFile } from './citation'

describe('BibTeX citation import', () => {
  it('returns editable citation text from a UTF-8 BibTeX file', async () => {
    const citation = '@article{example2026,\n  title = {Example dataset}\n}'
    const file = new File([citation], 'citation.bib', { type: 'application/x-bibtex' })

    await expect(citationTextFromBibtexFile(file)).resolves.toBe(citation)
  })

  it('rejects files that are not BibTeX', async () => {
    const file = new File(['Example citation'], 'citation.txt', { type: 'text/plain' })

    await expect(citationTextFromBibtexFile(file)).rejects.toThrow('.bib extension')
  })
})
