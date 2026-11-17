const repositoryUrl = 'https://github.com/example/adapter'
const found = { status: 'FOUND', has_croissant_file: true, repository_url: repositoryUrl, message: 'Croissant file found at repository root.' }
const success = { attempt_status: 'SUCCEEDED', registration_id: 'registration-1', adapter_id: 'example-adapter', adapter_name: 'Example Adapter', repository_location: repositoryUrl, published_version: '1.0.0', message: 'Registered version 1.0.0.', validation_errors: [] }

function streamReply(result: object, delay = 0) {
  return { delay, headers: { 'content-type': 'text/event-stream' }, body: `event: result\ndata: ${JSON.stringify({ type: 'result', result })}\n\n` }
}

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
    cy.tick(199)
    cy.then(() => expect(checks).to.equal(0))
    cy.tick(1)
    cy.wait('@preflight')
    cy.contains('button', 'Register adapter').should('be.enabled')
    repositoryInput().type('{backspace}', { delay: 0 }).type('r', { delay: 0 })
    cy.contains('button', 'Register adapter').should('be.disabled')
    cy.tick(200)
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
    cy.tick(200)
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
    cy.tick(200)
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

  it('shows the failed result and retries the initial request without a registration ID', () => {
    const bodies: unknown[] = []
    cy.intercept('GET', '**/registrations/croissant-file-present-check*', { body: found }).as('preflight')
    cy.intercept('POST', '**/api/v1/registrations/stream', (request) => {
      bodies.push(request.body)
      request.reply(bodies.length === 1 ? streamReply({
        attempt_status: 'FAILED', registration_id: null, published_version: null,
        message: 'The metadata failed the adapter schema check.', reason_code: 'SCHEMA_INVALID', validation_errors: ['Missing license.', 'Missing description.'],
      }, 300) : streamReply(success, 300))
    }).as('register')
    cy.intercept('POST', '**/registrations/*/process', () => { throw new Error('Registration must not make a second process request') })
    cy.visit('/register')
    repositoryInput().type(repositoryUrl, { delay: 0 })
    cy.wait('@preflight')
    cy.contains('button', 'Register adapter').click()
    cy.contains('Checking your adapter...').should('be.visible')
    cy.contains('h2', 'Registration details').should('not.exist')
    cy.wait('@register')
    cy.contains('Registration failed').should('be.visible')
    cy.location('pathname').should('equal', '/register')
    cy.contains('Your adapter has not been registered yet.').should('be.visible')
    cy.contains('dt', 'Registration status').parent().should('contain', 'FAILED - Schema validation failed')
    cy.contains('dt', 'Repository').parent().should('contain', repositoryUrl)
    cy.contains('The metadata failed the adapter schema check.').should('be.visible')
    cy.contains('button', 'Edit details').should('not.exist')
    cy.contains('button', 'View details').should('not.exist')
    cy.contains('dt', 'Reason code').parent().should('contain', 'SCHEMA_INVALID')
    cy.contains('li', 'Missing license.').should('be.visible')
    cy.contains('li', 'Missing description.').should('be.visible')
    cy.get('dialog[open]').should('not.exist')
    cy.contains('h2', 'Registration details').should('not.exist')
    cy.contains('Registration ID').should('not.exist')
    cy.contains('button', 'Retry registration').click()
    cy.contains('button', 'Retrying...').should('be.disabled')
    cy.contains('h2', 'Registration details').should('not.exist')
    cy.wait('@register')
    cy.contains('Adapter registered successfully').should('be.visible')
    cy.contains('dt', 'Registration status').parent().should('contain', 'Registered')
    cy.then(() => expect(bodies[0]).to.deep.equal(bodies[1]))
  })

  for (const failure of [
    { reason_code: 'INVALID_JSON', status: 'FAILED - Invalid JSON', message: 'Metadata must be UTF-8 encoded JSON.' },
    { reason_code: null, status: 'FAILED - Not registered', message: 'Registration could not be completed.' },
    { reason_code: 'NEW_BACKEND_REASON', status: 'FAILED - Not registered', message: 'The repository could not be processed.' },
  ]) {
    it(`preserves the backend message and details for ${failure.reason_code ?? 'a missing reason'}`, () => {
      cy.intercept('GET', '**/registrations/croissant-file-present-check*', { body: found }).as('preflight')
      cy.intercept('POST', '**/api/v1/registrations/stream', streamReply({
        attempt_status: 'FAILED', registration_id: null, published_version: null,
        reason_code: failure.reason_code, message: failure.message, validation_errors: [],
      })).as('register')
      cy.visit('/register')
      repositoryInput().type(repositoryUrl, { delay: 0 })
      cy.wait('@preflight')
      cy.contains('button', 'Register adapter').click()
      cy.wait('@register')
      cy.contains('dt', 'Registration status').parent().should('contain', failure.status)
      cy.contains(failure.message).should('be.visible')
      cy.contains('dt', 'Reason code').parent().should('contain', failure.reason_code ?? 'Not provided')
      cy.contains('Validation errors (0)').should('not.exist')
    })
  }

  it('deduplicates legacy errors using trimmed text while preserving wording and order', () => {
    const message = "'keywords' is a required property"
    const errors = [` ${message} `, '   ', message, 'Invalid  value', 'Invalid value', 'invalid value', 'Invalid value']
    cy.intercept('GET', '**/registrations/croissant-file-present-check*', { body: found }).as('preflight')
    cy.intercept('POST', '**/api/v1/registrations/stream', streamReply({
      attempt_status: 'FAILED', message, reason_code: 'SCHEMA_INVALID', validation_errors: errors,
    })).as('register')
    cy.visit('/register')
    repositoryInput().type(repositoryUrl, { delay: 0 })
    cy.wait('@preflight')
    cy.contains('button', 'Register adapter').click()
    cy.wait('@register')
    cy.contains('h3', /^Message$/).should('not.exist')
    cy.contains('h3', 'Validation errors (4)').parent().find('li > p').then(($messages) => {
      expect([...$messages].map((element) => element.textContent)).to.deep.equal([
        ` ${message} `, 'Invalid  value', 'Invalid value', 'invalid value',
      ])
    })
  })

  it('renders structured diagnostics inline while preserving different locations and unmatched text errors', () => {
    const message = "'keywords' is a required property"
    const keywordDetail = {
      message, json_path: '$.keywords', requirement: 'Required property', expected_format: 'An array containing at least one non-empty string',
      location_description: 'Add the missing field "keywords" to the top-level object (inside the outer { ... } braces).',
      source_file: 'croissant.jsonld', source_url: `${repositoryUrl}/blob/${'a'.repeat(40)}/croissant.jsonld`,
      line: 3, column: 1, location_kind: 'containing_object',
    }
    cy.intercept('GET', '**/registrations/croissant-file-present-check*', { body: found }).as('preflight')
    cy.intercept('POST', '**/api/v1/registrations/stream', streamReply({
      attempt_status: 'FAILED', message, reason_code: 'SCHEMA_INVALID',
      validation_errors: [message, 'Croissant problem', 'Invalid type'],
      validation_details: [keywordDetail, keywordDetail,
        { message: 'Invalid type', json_path: '$.hasPart[0].name', requirement: 'Value type', expected_format: 'A string', line: 6, column: 9, location_kind: 'value' },
        { message: 'Invalid type', json_path: '$.hasPart[1].name', requirement: 'Value type', expected_format: 'A string' },
      ],
    })).as('register')
    cy.visit('/register')
    repositoryInput().type(repositoryUrl, { delay: 0 })
    cy.wait('@preflight')
    cy.contains('button', 'Register adapter').click()
    cy.wait('@register')
    cy.contains('h3', /^Message$/).should('not.exist')
    cy.contains('h3', 'Validation errors (4)').parent().within(() => {
      cy.get('li').should('have.length', 4)
      cy.contains('$.keywords').should('be.visible')
      cy.contains('Required property').should('be.visible')
      cy.contains(keywordDetail.expected_format).should('be.visible')
      cy.contains(keywordDetail.location_description).should('be.visible')
      cy.contains('Containing object starts at line 3, column 1.').should('be.visible')
      cy.contains('The missing field has no existing line.').should('be.visible')
      cy.contains('a', 'croissant.jsonld').should('have.attr', 'href', `${keywordDetail.source_url}#L3`)
      cy.contains('Line 6, column 9.').should('be.visible')
      cy.contains('li', 'Croissant problem').find('dl').should('not.exist')
      cy.contains('$.hasPart[0].name').should('be.visible')
      cy.contains('$.hasPart[1].name').should('be.visible')
    })
  })

  it('shows one fallback when no message or usable validation errors are returned', () => {
    cy.intercept('GET', '**/registrations/croissant-file-present-check*', { body: found }).as('preflight')
    cy.intercept('POST', '**/api/v1/registrations/stream', streamReply({
      attempt_status: 'FAILED', message: '  ', validation_errors: ['', '  '], validation_details: [],
    })).as('register')
    cy.visit('/register')
    repositoryInput().type(repositoryUrl, { delay: 0 })
    cy.wait('@preflight')
    cy.contains('button', 'Register adapter').click()
    cy.wait('@register')
    cy.contains('No additional diagnostic information was returned.').should('be.visible')
    cy.contains('h3', /^Message$/).should('not.exist')
    cy.contains('h3', /Validation errors/).should('not.exist')
  })

  it('does not report a confirmed failure when the response is lost', () => {
    cy.intercept('GET', '**/registrations/croissant-file-present-check*', { body: found }).as('preflight')
    cy.intercept('POST', '**/api/v1/registrations/stream', { forceNetworkError: true }).as('register')
    cy.visit('/register')
    repositoryInput().type(repositoryUrl, { delay: 0 })
    cy.wait('@preflight')
    cy.contains('button', 'Register adapter').click()
    cy.wait('@register')
    cy.contains('Registration outcome could not be confirmed').should('be.visible')
    cy.contains('Registration failed').should('not.exist')
    cy.contains('button', 'Register adapter').should('not.exist')
    cy.contains('button', 'Retry registration').should('not.exist')
  })
})
