const repositoryCheckRoute = '**/api/v1/registrations/croissant-file-present-check*'
const connectionMessage = 'Unable to connect to service'
const repositoryLocation = 'https://github.com/biocypher/auto-submit-adapter'
const validatedRepositoryLocation = `${repositoryLocation}-missing-valid`


function repositoryInput() {
  return cy.contains('label', 'Repository location').find('input')
}

describe('Sign in allows/disallows registration etc', () => {
  beforeEach(() => {
    cy.intercept('GET', '**/api/v1/auth/me', { forceNetworkError: true })
    cy.intercept('GET', '**/api/v1/health', { forceNetworkError: true })
    cy.intercept('GET', repositoryCheckRoute, { forceNetworkError: true }).as('repositoryCheck')
    cy.intercept('POST', '**/api/v1/registrations', { statusCode: 503 }).as('createRegistration')
  })

  it('blocks sign-in return submission until the edited URL passes a fresh check', () => {
    cy.intercept('GET', '**/api/v1/auth/me', { body: { authenticated: true } })
    cy.intercept('GET', repositoryCheckRoute, { delay: 6000, body: { has_croissant_file: true } })
    cy.visit('/register', {
      onBeforeLoad(window) {
        window.localStorage.setItem('bcr-register-draft', JSON.stringify({ repositoryLocation }))
        window.localStorage.setItem('bcr-register-submit-after-auth', '1')
      },
    })
    cy.get('button[type="submit"]').should('be.disabled')
    cy.contains(connectionMessage, { timeout: 6500 }).should('be.visible')
    cy.get('button[type="submit"]').should('be.disabled')
    cy.get('@createRegistration.all').should('have.length', 0)
    cy.intercept('GET', repositoryCheckRoute, { body: { has_croissant_file: false } })
    repositoryInput().type('-missing')
    cy.contains('Croissant file not found').should('be.visible')
    cy.get('button[type="submit"]').should('be.disabled')
    cy.get('@createRegistration.all').should('have.length', 0)
    cy.intercept({
      method: 'GET',
      pathname: '/api/v1/registrations/croissant-file-present-check',
      query: { repository_url: validatedRepositoryLocation },
    }, { body: { has_croissant_file: true } })
    repositoryInput().type('-valid')
    cy.contains('Croissant file found at repository root').should('be.visible')
    cy.get('button[type="submit"]').should('be.enabled')
    cy.get('@createRegistration.all').should('have.length', 0)
    cy.get('button[type="submit"]').click()
    cy.wait('@createRegistration').its('request.body.repository_location').should('equal', validatedRepositoryLocation)
    cy.contains('Registration failed.').should('be.visible')
    cy.get('@createRegistration.all').should('have.length', 1)
  })
})
