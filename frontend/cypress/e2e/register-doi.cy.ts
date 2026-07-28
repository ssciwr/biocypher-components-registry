const doi = '10.5555/12345678'

describe('registration DOI check', () => {
  it('strips doi prefix and checks Crossref on blur', () => {
    cy.intercept('GET', '**/api/v1/auth/me', { statusCode: 401, body: { detail: 'GitHub sign-in required.' } })
    cy.intercept('GET', `**/works/${encodeURIComponent(doi)}`, { body: { message: {} } }).as('doiCheck')
    cy.visit('/register')
    cy.contains('label', 'DOI').find('input').type(` doi: ${doi} `).blur()
    cy.wait('@doiCheck')
    cy.contains('DOI found in Crossref').should('be.visible')
    cy.contains('Make sure it fits this format').should('not.exist')
    cy.contains('label', 'DOI').find('input').should('have.value', doi)
  })
})
