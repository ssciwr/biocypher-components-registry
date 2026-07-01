const doi = '10.5555/12345678'
const citationCount = 15
const expectedCitationCount = 15

const adapter = {
  adapter_id: 'crossref-test-adapter',
  adapter_name: 'Crossref Test Adapter',
  doi,
  cff_url: null,
}

const crossrefWork = {
  message: {
    title: ['Mocked Crossref work'],
    author: [{ name: 'Crossref Tester' }],
    'is-referenced-by-count': citationCount,
  },
}

describe('Crossref citation endorsement test', () => {
  it('shows successful GET made on load and data parsed onto page, crossref citation data for an adapter DOI appears from client-side crossref API request ', () => {
    cy.intercept('GET', '**/api/v1/auth/me', { statusCode: 401, body: { detail: 'GitHub sign-in required.' } })
    cy.intercept('GET', '**/api/v1/adapters/crossref-test-adapter', { body: adapter })
    cy.intercept('GET', `https://api.crossref.org/works/${encodeURIComponent(doi)}`, { body: crossrefWork }).as('crossrefWork')

    cy.visit('/adapters/crossref-test-adapter')
    cy.wait('@crossrefWork')
    cy.contains('section', 'Cite').within(() => {
      cy.contains('Cited by').should('be.visible')
      cy.contains('p', new RegExp(`^${expectedCitationCount}$`)).should('be.visible') // is-referenced-by-count output from crossref.
      cy.contains('p', /^0$/).should('not.exist')
      cy.contains('p', /^15$/).should('exist')
      cy.contains('Mocked Crossref work').should('be.visible')
    })
  })
})
