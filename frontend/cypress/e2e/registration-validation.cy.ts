
function pressEnter() {
  // Include the carriage-return text so Chromium performs native button activation.
  cy.then(() => Cypress.automation('remote:debugger:protocol', {
    command: 'Input.dispatchKeyEvent',
    params: { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: '\r', unmodifiedText: '\r' },
  }))
  cy.then(() => Cypress.automation('remote:debugger:protocol', {
    command: 'Input.dispatchKeyEvent',
    params: { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 },
  }))
}

const repo = 'https://github.com/example/adapter'
const message = "'keywords' is a required property"
const detail = {
  message, json_path: '$.keywords', requirement: 'Required property',
  expected_format: 'An array containing at least one non-empty string',
  location_description: 'Add the missing field "keywords" to the top-level object.',
  source_file: 'croissant.jsonld', source_url: `${repo}/blob/${'a'.repeat(40)}/croissant.jsonld`,
  line: 1, column: 1, location_kind: 'containing_object',
}
const checks = [
  { id: 'file', name: 'File retrieval and JSON parsing', status: 'PASSED' },
  { id: 'croissant', name: 'Croissant compliance', status: 'PASSED', validator_name: 'mlcroissant', validator_version: '1.0.22' },
  { id: 'schema', name: 'Adapter schema', status: 'FAILED', profile_version: 'v1', schema_title: 'BioCypher Adapter Croissant Schema v1', schema_dialect: 'http://json-schema.org/draft-07/schema#', errors: [message, ` ${message} `], validation_details: [detail, detail] },
  { id: 'semantics', name: 'Adapter semantics', status: 'PASSED' },
  { id: 'datasets', name: 'Embedded datasets', status: 'FAILED' },
  { id: 'dataset:0', parent_id: 'datasets', dataset_index: 0, name: 'Same name', status: 'FAILED', validator_name: 'mlcroissant', validator_version: '1.0.22', errors: ['Dataset problem'] },
  { id: 'dataset:1', parent_id: 'datasets', dataset_index: 1, name: 'Same name', status: 'FAILED', validator_name: 'mlcroissant', validator_version: '1.0.22', errors: ['Dataset problem'] },
]
const result = { attempt_status: 'FAILED', message, reason_code: 'SCHEMA_INVALID', validation_errors: [message, 'Dataset problem'], validation_details: [detail], validation_checks: checks, profile_version: 'v1' }
const encode = (type: string, data: object) => `event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`

function submit() {
  cy.contains('label', 'Repository location').find('input').type(repo, { delay: 0 })
  cy.wait('@preflight')
  cy.contains('button', 'Register adapter').click()
}

describe('registration validation breakdown', () => {
  beforeEach(() => {
    cy.intercept('GET', '**/api/v1/auth/me', { body: { authenticated: true } })
    cy.intercept('GET', '**/api/v1/health', { body: { status: 'ok' } })
    cy.intercept('GET', '**/croissant-file-present-check*', { body: { status: 'FOUND', has_croissant_file: true, repository_url: repo, message: 'Croissant file found at repository root.' } }).as('preflight')
  })

  it('keeps each check and dataset separate, with inline diagnostics and a lazy schema viewer', () => {
    cy.intercept('POST', '**/registrations/stream', { headers: { 'content-type': 'text/event-stream' }, body: encode('result', { result }) }).as('registration')
    let loads = 0
    cy.intercept('GET', '**/schemas/v1', request => {
      loads++
      request.reply(loads === 1 ? { statusCode: 503, body: {} } : { body: { title: 'BioCypher Adapter Croissant Schema v1', required: ['keywords'] } })
    }).as('schema')
    cy.visit('/register')
    submit()
    cy.wait('@registration')
    cy.get('[data-check-id="file"]').should('contain', 'Passed')
    cy.get('[data-check-id="schema"]').should('contain', 'Failed').and('contain', 'v1')
    cy.get('[data-check-id="schema"] li > p').should('have.length', 1)
    cy.contains('The missing field has no existing line.').should('be.visible')
    cy.contains('h3', /^Message$/).should('not.exist')
    cy.get('[data-check-id="dataset:0"]').should('contain', 'Dataset 1').and('contain', 'Same name')
    cy.get('[data-check-id="dataset:1"]').should('contain', 'Dataset 2').and('contain', 'Same name')
    cy.get('li > p').filter((_, el) => el.textContent === 'Dataset problem').should('have.length', 2)
    cy.then(() => expect(loads).to.equal(0))
    cy.contains('summary', 'View schema').click()
    cy.wait('@schema')
    cy.contains('button', 'Retry schema loading').click()
    cy.wait('@schema')
    cy.contains('JSON Schema dialect: Draft 7').should('be.visible')
    cy.get('pre').should('contain', 'keywords')
    cy.get('[data-check-id="schema"]').should('contain', 'Failed')
    cy.contains('button', 'View details').should('not.exist')
    cy.contains('button', 'Collapse checks').should('have.attr', 'aria-expanded', 'true').click()
    cy.get('table').should('not.be.visible')
    cy.contains('h3', 'Validation checks').should('be.visible')
    cy.contains('3 failed checks').should('be.visible')
    cy.contains('button', 'Expand checks').should('have.attr', 'aria-expanded', 'false').focus()
    cy.focused().should('contain', 'Expand checks')
    pressEnter()
    cy.get('table').should('be.visible')
    cy.contains('The missing field has no existing line.').should('be.visible')
    cy.get('[data-check-id="schema"] li > p').should('have.length', 1)
  })

  it('shows progress before the terminal result without making a second request', () => {
    let posts = 0
    cy.visit('/register', { onBeforeLoad(win) {
      const originalFetch = win.fetch.bind(win)
      win.fetch = async (input, init) => {
        const request = new Request(input, init)
        if (!new URL(request.url).pathname.endsWith('/registrations/stream')) return originalFetch(input, init)
        posts++
        const encoder = new TextEncoder()
        return new Response(new ReadableStream({ start(controller) {
          controller.enqueue(encoder.encode(encode('snapshot', { checks: checks.map(check => ({ ...check, status: 'PENDING', errors: [], validation_details: [] })) })))
          controller.enqueue(encoder.encode(encode('check', { check: { id: 'file', name: 'File retrieval and JSON parsing', status: 'RUNNING' } })))
          win.setTimeout(() => {
            controller.enqueue(encoder.encode(encode('result', { result })))
            controller.close()
          }, 1200)
        } }), { headers: { 'content-type': 'text/event-stream' } })
      }
    } })
    submit()
    cy.get('[data-check-id="file"]').should('contain', 'Running')
    cy.get('[data-check-id="schema"]').should('contain', 'Pending')
    cy.contains('Registration failed').should('be.visible')
    cy.get('[data-check-id="schema"]').should('contain', 'Failed')
    cy.then(() => expect(posts).to.equal(1))
  })

  it('keeps interrupted checks unconfirmed without reconnecting or offering a blind retry', () => {
    let posts = 0
    cy.intercept('POST', '**/registrations/stream', request => {
      posts++
      request.reply({ headers: { 'content-type': 'text/event-stream' }, body: encode('snapshot', { checks: [{ id: 'file', name: 'File retrieval and JSON parsing', status: 'RUNNING' }] }) })
    }).as('registration')
    cy.visit('/register')
    submit()
    cy.wait('@registration')
    cy.contains('Registration outcome could not be confirmed').should('be.visible')
    cy.get('[data-check-id="file"]').should('contain', 'Unconfirmed')
    cy.contains('Registration failed').should('not.exist')
    cy.contains('button', 'Retry registration').should('not.exist')
    cy.wait(500)
    cy.then(() => expect(posts).to.equal(1))
  })
})
