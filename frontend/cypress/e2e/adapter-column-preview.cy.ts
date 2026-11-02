// Mock data

const fields = [
  { name: 'source', dataType: 'sc:Text', examples: ['P0DP25'], description: 'Source molecular entity.' },
  { name: 'target', dataType: 'https://schema.org/Text', examples: ['P48995', 'P99999'], description: 'Primary reference identifier of the target molecular entity.' },
  { name: 'is_directed', dataType: 'cr:Int64', examples: [1, 0], description: 'The interaction has a causal direction.' },
  { name: 'omnipath', dataType: { '@id': 'sc:Boolean' }, examples: [false, true], description: 'Supported by the OmniPath dataset.' },
  { name: 'evidences', dataType: ['sc:Text', 'custom:JSON'], examples: [{ resource: 'TRIP', references: ['12601176', '11290752'] }], description: 'Resource and literature information.' },
  { name: 'uncurated' },
]
const strengthField = { name: 'strength', dataType: 'cr:Float32', examples: 1.5, description: 'Interaction strength.' }
const networkDataset = { name: ' Networks ', recordSet: [{ field: fields }, { field: strengthField }] }
const metadata = {
  adapter_id: 'column-preview',
  registry_entry_id: 'entry-1',
  metadata: { hasPart: [
    { name: 'Annotations', recordSet: { field: { name: 'annotation_only' } } },
    networkDataset,
  ] },
}
const adapter = {
  adapter_id: 'column-preview',
  adapter_name: 'Column Preview Adapter',
  data_sources: [{ name: 'Networks', column_count: 7 }],
}

// End Mock data

function openPreview() {
  cy.contains('button', '7 Columns').click()
}

function searchColumns(query: string) {
  cy.get('input[aria-label="Search columns"]').clear().type(query, { parseSpecialCharSequences: false })
}

const columnSearchCases = [
  [' IS_ DIRE CTED ', ['is_directed']],
  [' BOO LEAN ', ['omnipath']],
  [' P 48995 ', ['target']],
  [' primary REFERENCE ', ['target']],
  [' TR IP ', ['evidences']],
  ['1129 0752', ['evidences']],
  [' S O U R C E ', ['source', 'evidences']],
  [' TEXT P0DP25 ', ['source']],
] as const

// Yes this is code to check against the code but it works here for this search case.
function expectColumnSearch(query: string, columnNames: readonly string[]) {
  searchColumns(query)
  cy.get('tbody th').should(($fields) => expect($fields.toArray().map((field) => field.textContent)).to.deep.equal(columnNames))
}

// Does the column preview show the right data in react from our mocked API route?
describe('adapter column preview', () => {
  beforeEach(() => {
    cy.viewport(1200, 700)
    cy.intercept('GET', '**/api/v1/auth/me', { statusCode: 401 })
    cy.intercept('GET', '**/api/v1/adapters/column-preview', { body: adapter })
    cy.intercept('GET', '**/api/v1/adapters/column-preview/metadata', { body: metadata })
    cy.visit('/adapters/column-preview')
  })

  it('Column data is visibiel', () => {
    openPreview()
    cy.get('dialog h2').should('have.text', 'Data Source "Networks" - 7 Columns')
    cy.get('tbody tr').should('have.length', 7)
    cy.contains('tbody tr', 'target').should('contain.text', 'https://schema.org/Text').and('contain.text', 'P48995\nP99999').and('contain.text', 'Primary reference identifier')
    cy.get('table').should('not.contain.text', 'annotation_only')
    cy.screenshot('column-preview-desktop', { capture: 'viewport' })
    // Test mobile compataibility
    cy.viewport(390, 700)
    cy.get('table').parent().should(($scrollArea) => expect($scrollArea[0].scrollWidth).to.be.greaterThan($scrollArea[0].clientWidth))
    cy.screenshot('column-preview-mobile', { capture: 'viewport' })
    cy.get('dialog button[aria-label="Close modal"]').last().click()
    cy.intercept('GET', '**/api/v1/adapters/column-preview/metadata', { delay: 6000, body: metadata })
    openPreview()
    cy.get('[role="status"]', { timeout: 6500 }).should('have.text', 'Service not available presently, sorry. Please try again later.')
    cy.get('tbody th').should('not.exist')
  })

  it('Spaces are ignored during searches with a search case', () => {
    openPreview()
    cy.get('tbody tr').should('have.length', 7) // before any searches
    columnSearchCases.forEach(([query, columnNames]) => expectColumnSearch(query, columnNames))
    searchColumns('targ')
    cy.get('tbody tr').should('have.length', 1)
    cy.get('tbody th').should('have.text', 'target')
    searchColumns('stringP0DP25')
    cy.get('[role="status"]').should('have.text', 'No columns match your search.')
    cy.get('tbody th').should('not.exist') // no matches
    searchColumns('   ')
    cy.get('tbody tr').should('have.length', 7) // same "before", null search basically
  })
})
