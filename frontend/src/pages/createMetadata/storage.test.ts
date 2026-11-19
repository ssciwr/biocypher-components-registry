import { describe, expect, it } from 'vitest'
import { hasMeaningfulMetadataDraft } from './storage'

describe('metadata draft persistence', () => {
  it('does not treat an empty form as a resumable session', () => {
    expect(hasMeaningfulMetadataDraft({
      adapterId: '',
      codeRepository: '',
      creators: [],
      datasets: [],
      description: '',
      keywords: '',
      license: '',
      name: '',
      version: '',
    })).toBe(false)
  })

  it('recognizes a previous session after meaningful input was saved', () => {
    expect(hasMeaningfulMetadataDraft({ name: 'Resumable adapter' })).toBe(true)
    expect(hasMeaningfulMetadataDraft({ creators: [{ name: 'Ada' }] })).toBe(true)
    expect(hasMeaningfulMetadataDraft({ datasets: [{ name: 'People' }] })).toBe(true)
  })
})
