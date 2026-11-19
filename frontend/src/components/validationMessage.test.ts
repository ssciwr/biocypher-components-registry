import { describe, expect, it } from 'vitest'
import { formatValidatorMessage } from './validationMessage'

describe('validator message formatting', () => {
  it('separates URI alternatives without changing validator words or values', () => {
    const message = 'Extract should have one of the following properties http://mlcommons.org/croissant/column or http://mlcommons.org/croissant/fileProperty or http://mlcommons.org/croissant/jsonPath.'

    expect(formatValidatorMessage(message)).toEqual({
      prefix: 'Extract should have one of the following properties',
      alternatives: [
        'http://mlcommons.org/croissant/column',
        'http://mlcommons.org/croissant/fileProperty',
        'http://mlcommons.org/croissant/jsonPath',
      ],
      suffix: '.',
    })
  })

  it('leaves messages without a URI alternative list untouched', () => {
    expect(formatValidatorMessage('The current JSON-LD is invalid.')).toBeNull()
  })

  it('does not restructure URLs joined by prose other than or', () => {
    expect(formatValidatorMessage('Compare https://example.org/one with https://example.org/two.')).toBeNull()
  })
})
