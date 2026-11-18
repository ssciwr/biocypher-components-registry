import { describe, expect, it } from 'vitest'
import { citationTextFromBibtexFile } from './citation'

describe('BibTeX citation import', () => {
  it.each(['citation.bib', 'citation.bibtex', 'citation.BIBTEX'])('returns editable citation text from %s', async (filename) => {
    const citation = '@article{example2026,\n  title = {Example dataset}\n}'
    const file = new File([citation], filename, { type: 'application/x-bibtex' })

    await expect(citationTextFromBibtexFile(file)).resolves.toBe(citation)
  })

  it('rejects files that are not BibTeX', async () => {
    const file = new File(['Example citation'], 'citation.txt', { type: 'text/plain' })

    await expect(citationTextFromBibtexFile(file)).rejects.toThrow('.bib or .bibtex extension')
  })
})
