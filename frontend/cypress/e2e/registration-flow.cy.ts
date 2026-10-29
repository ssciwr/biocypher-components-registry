const repositoryUrl = 'https://github.com/example/adapter'
const found = { status: 'FOUND', has_croissant_file: true, repository_url: repositoryUrl, message: 'Croissant file found at repository root.' }
const success = { attempt_status: 'SUCCEEDED', registration_id: 'registration-1', adapter_id: 'example-adapter', adapter_name: 'Example Adapter', repository_location: repositoryUrl, published_version: '1.0.0', message: 'Registered version 1.0.0.', validation_errors: [] }

function repositoryInput() {
  return cy.contains('label', 'Repository location').find('input')
}

describe('automatic pre-flight and synchronous registration', () => {
  beforeEach(() => {
    cy.intercept('GET', '**/api/v1/auth/me', { body: { authenticated: true } })
    cy.intercept('GET', '**/api/v1/health', { body: { status: 'ok' } })
  })

  it('debounces checks and rechecks when the original URL is restored', () => {
    let checks = 0
    cy.intercept('GET', '**/registrations/croissant-file-present-check*', (request) => {
      checks += 1
      request.reply(found)
    }).as('preflight')
    cy.visit('/register')
    cy.clock()
    repositoryInput().type(repositoryUrl, { delay: 0 })
    cy.contains('button', 'Register adapter').should('be.disabled')
    cy.tick(499)
    cy.then(() => expect(checks).to.equal(0))
    cy.tick(1)
    cy.wait('@preflight')
    cy.contains('button', 'Register adapter').should('be.enabled')
    repositoryInput().type('{backspace}', { delay: 0 }).type('r', { delay: 0 })
    cy.contains('button', 'Register adapter').should('be.disabled')
    cy.tick(500)
    cy.wait('@preflight')
    cy.then(() => expect(checks).to.equal(2))
    cy.contains('button', 'Register adapter').should('be.enabled')
  })

  it('shows actionable unavailability instead of claiming the file is absent', () => {
    cy.intercept('GET', '**/registrations/croissant-file-present-check*', { body: {
      status: 'UNAVAILABLE', reason_code: 'REPOSITORY_UNAVAILABLE', has_croissant_file: false,
      repository_url: repositoryUrl, message: 'Repository access is restricted.',
    } }).as('preflight')
    cy.visit('/register')
    repositoryInput().type(repositoryUrl, { delay: 0 })
    cy.wait('@preflight')
    cy.contains('Repository access is restricted.').should('be.visible')
    cy.contains('button', 'Register adapter').should('be.disabled')
    cy.contains('Croissant file not found').should('not.exist')
  })

  it('ignores an older successful response after the URL changes', () => {
    let oldCheckStarted = false
    cy.intercept('GET', '**/registrations/croissant-file-present-check*', (request) => {
      if (request.query.repository_url === repositoryUrl) {
        oldCheckStarted = true
        request.reply({ delay: 1800, body: found })
      } else {
        request.alias = 'newCheck'
        request.reply({ ...found, status: 'NOT_FOUND', has_croissant_file: false })
      }
    })
    cy.visit('/register')
    repositoryInput().type(repositoryUrl, { delay: 0 })
    cy.wrap(null).should(() => expect(oldCheckStarted).to.equal(true))
    repositoryInput().clear().type(`${repositoryUrl}-other`, { delay: 0 })
    cy.wait('@newCheck')
    cy.contains('Croissant file not found at repository root').should('be.visible')
    // Wait beyond the old response delay to prove it cannot re-enable submission.
    cy.wait(1900)
    cy.contains('button', 'Register adapter').should('be.disabled')
    cy.contains('Croissant file not found at repository root').should('be.visible')
  })

  it('automatically retries a transient check failure', () => {
    let checks = 0
    cy.intercept('GET', '**/registrations/croissant-file-present-check*', (request) => {
      checks += 1
      request.reply(checks === 1 ? { ...found, status: 'UNAVAILABLE', reason_code: 'REMOTE_TEMPORARY', has_croissant_file: false } : found)
    }).as('preflight')
    cy.visit('/register')
    cy.clock()
    repositoryInput().type(repositoryUrl, { delay: 0 })
    cy.tick(500)
    cy.wait('@preflight')
    cy.contains('button', 'Register adapter').should('be.disabled')
    cy.tick(1000)
    cy.wait('@preflight')
    cy.contains('button', 'Register adapter').should('be.enabled')
    cy.then(() => expect(checks).to.equal(2))
  })

  it('stops after two automatic retries of a transient failure', () => {
    let checks = 0
    cy.intercept('GET', '**/registrations/croissant-file-present-check*', (request) => {
      checks += 1
      request.reply({ ...found, status: 'UNAVAILABLE', reason_code: 'REMOTE_TEMPORARY', has_croissant_file: false, message: 'Host temporarily unavailable.' })
    }).as('preflight')
    cy.visit('/register')
    cy.clock()
    repositoryInput().type(repositoryUrl, { delay: 0 })
    cy.tick(500)
    cy.wait('@preflight')
    cy.tick(1000)
    cy.wait('@preflight')
    cy.tick(2000)
    cy.wait('@preflight')
    cy.contains('Host temporarily unavailable.').should('be.visible')
    cy.tick(10000)
    cy.then(() => expect(checks).to.equal(3))
    cy.contains('button', 'Register adapter').should('be.disabled')
  })

  it('keeps the failed form and retries the initial request without a registration ID', () => {
    const bodies: unknown[] = []
    cy.intercept('GET', '**/registrations/croissant-file-present-check*', { body: found }).as('preflight')
    cy.intercept('POST', '**/api/v1/registrations', (request) => {
      bodies.push(request.body)
      request.reply(bodies.length === 1 ? { body: {
        attempt_status: 'FAILED', registration_id: null, published_version: null,
        message: 'Missing license.', reason_code: 'SCHEMA_INVALID', validation_errors: ['Missing license.'],
      } } : { delay: 300, statusCode: 201, body: success })
    }).as('register')
    cy.intercept('POST', '**/registrations/*/process', () => { throw new Error('Registration must not make a second process request') })
    cy.visit('/register')
    repositoryInput().type(repositoryUrl, { delay: 0 })
    cy.wait('@preflight')
    cy.contains('button', 'Register adapter').click()
    cy.wait('@register')
    cy.contains('Registration failed').should('be.visible')
    repositoryInput().should('have.value', repositoryUrl)
    cy.contains('button', 'Retry registration').click()
    cy.contains('button', 'Retrying...').should('be.disabled')
    cy.wait('@register')
    cy.contains('Adapter registration successful').should('be.visible')
    cy.contains('SUCCEEDED').should('be.visible')
    cy.then(() => expect(bodies[0]).to.deep.equal(bodies[1]))
  })

  it('does not report a confirmed failure when the response is lost', () => {
    cy.intercept('GET', '**/registrations/croissant-file-present-check*', { body: found }).as('preflight')
    cy.intercept('POST', '**/api/v1/registrations', { forceNetworkError: true }).as('register')
    cy.visit('/register')
    repositoryInput().type(repositoryUrl, { delay: 0 })
    cy.wait('@preflight')
    cy.contains('button', 'Register adapter').click()
    cy.wait('@register')
    cy.contains('Could not confirm the registration result').should('be.visible')
    cy.contains('Registration failed').should('not.exist')
    cy.contains('button', 'Register adapter').should('be.enabled')
  })
})
