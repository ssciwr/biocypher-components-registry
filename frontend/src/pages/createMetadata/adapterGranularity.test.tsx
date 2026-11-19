import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AdapterDetailsStep } from './MetadataGeneratorSteps'
import { emptyForm, emptyCreator } from './options'
import { hasMeaningfulMetadataDraft } from './storage'

describe('adapter granularity', () => {
  it('offers adapter granularities with accessible help and no component-type selector', () => {
    const markup = renderToStaticMarkup(<AdapterDetailsStep
      creatorActionLabel="Add creator"
      creatorDraft={emptyCreator}
      form={{ ...emptyForm, granularity: 'Secondary' }}
      isEditingCreator={false}
      onAddCreator={() => {}}
      onCreatorDraftChange={() => {}}
      onEditCreator={() => {}}
      onFormChange={() => {}}
      onRemoveCreator={() => {}}
    />)
    expect(markup).toContain('Help for Adapter granularity')
    expect(markup).toContain('single atomic resource')
    expect(markup).toContain('composite resource')
    expect(markup).toContain('<option value="Secondary" selected="">Secondary</option>')
    expect(markup).not.toContain('Component type')
    expect(markup).not.toContain('<option value="pipeline"')
  })

  it('recognizes a draft containing only an explicitly selected granularity', () => {
    expect(hasMeaningfulMetadataDraft({ granularity: 'Primary' })).toBe(true)
    expect(hasMeaningfulMetadataDraft({ granularity: '' })).toBe(false)
  })
})
