const repositoryCheckRoute = '**/api/v1/registrations/croissant-file-present-check*'
const connectionMessage = 'Unable to connect to service'
const repositoryLocation = 'https://github.com/biocypher/auto-submit-adapter'
const validatedRepositoryLocation = `${repositoryLocation}-missing-valid`

function repositoryInput() {
  return cy.contains('label', 'Repository location').find('input')
}

describe('repository checks when returning from sign-in', () => {
  beforeEach(() => {
    cy.intercept('GET', '**/api/v1/auth/me', { forceNetworkError: true })
    cy.intercept('GET', '**/api/v1/health', { forceNetworkError: true })
    cy.intercept('GET', repositoryCheckRoute, { forceNetworkError: true }).as('repositoryCheck')
    cy.intercept('POST', '**/api/v1/registrations/stream', {
      statusCode: 400, body: { detail: 'Registration request rejected.' },
    }).as('createRegistration')
  })

  it('blocks sign-in return submission until the edited URL passes a fresh check', () => {
    cy.intercept('GET', '**/api/v1/auth/me', { body: { authenticated: true } })
    let originalCheckStarted = false
    cy.clock()
    cy.intercept('GET', repositoryCheckRoute, (request) => {
      originalCheckStarted = true
      request.reply({ delay: 15_000, body: {
        status: 'FOUND', repository_url: repositoryLocation,
        has_croissant_file: true, message: 'Croissant file found at repository root.',
      } })
    })
    cy.visit('/register', {
      onBeforeLoad(window) {
        window.localStorage.setItem('bcr-register-draft', JSON.stringify({ repositoryLocation }))
        window.localStorage.setItem('bcr-register-submit-after-auth', '1')
      },
    })
    cy.get('button[type="submit"]').should('be.disabled')
    cy.tick(200)
    cy.wrap(null).should(() => expect(originalCheckStarted).to.equal(true))
    cy.tick(65_000)
    cy.contains(connectionMessage).should('be.visible')
    cy.get('button[type="submit"]').should('be.disabled')
    cy.get('@createRegistration.all').should('have.length', 0)
    cy.intercept('GET', repositoryCheckRoute, { body: {
      status: 'NOT_FOUND', repository_url: `${repositoryLocation}-missing`,
      has_croissant_file: false, message: 'Could not find croissant.jsonld at the repository root. Ensure your metadata file has this exact filename, including the .jsonld extension.',
    } })
    repositoryInput().type('-missing', { delay: 0 })
    cy.tick(200)
    cy.contains('Could not find croissant.jsonld at the repository root. Ensure your metadata file has this exact filename, including the .jsonld extension.').should('be.visible')
    cy.get('button[type="submit"]').should('be.disabled')
    cy.get('@createRegistration.all').should('have.length', 0)
    cy.intercept({
      method: 'GET',
      pathname: '/api/v1/registrations/croissant-file-present-check',
      query: { repository_url: validatedRepositoryLocation },
    }, { body: {
      status: 'FOUND', repository_url: validatedRepositoryLocation,
      has_croissant_file: true, message: 'Croissant file found at repository root.',
    } })
    repositoryInput().type('-valid', { delay: 0 })
    cy.tick(200)
    cy.contains('Croissant file found at repository root').should('be.visible')
    cy.get('button[type="submit"]').should('be.enabled')
    cy.get('@createRegistration.all').should('have.length', 0)
    cy.get('button[type="submit"]').click()
    cy.wait('@createRegistration').its('request.body.repository_location').should('equal', validatedRepositoryLocation)
    cy.contains('Registration request rejected.').should('be.visible')
    cy.get('@createRegistration.all').should('have.length', 1)
  })
})
