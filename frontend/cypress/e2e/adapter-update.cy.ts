const adapter = {
  adapter_id: 'example-adapter', adapter_name: 'Example Adapter', version: '1.0.0',
  repository_location: 'https://github.com/example/adapter', description: 'Published description',
  can_delete: true, can_update: true, latest_attempt: null,
  endorsement_count: 0, endorsed_by_current_user: false, data_sources: [], keywords: [],
}
const failed = {
  attempt_status: 'FAILED', published_version: '1.0.0', update_applied: false,
  message: 'Missing license. Previous metadata retained.', reason_code: 'SCHEMA_INVALID', validation_errors: ['Missing license.'],
}

describe('adapter Update action', () => {
  beforeEach(() => {
    cy.intercept('GET', '**/api/v1/auth/me', { body: { authenticated: true } })
    cy.intercept('GET', '**/api/v1/health', { body: { status: 'ok' } })
  })

  it('places Update beside Delete and uses the same action to retry failed updates', () => {
    let attempts = 0
    const succeeded = { ...failed, attempt_status: 'SUCCEEDED', published_version: '1.1.0', update_applied: true, message: 'Updated from 1.0.0 to 1.1.0.', reason_code: null, validation_errors: [] }
    cy.intercept('GET', '**/api/v1/adapters/example-adapter', (request) => {
      request.reply({ ...adapter, version: attempts > 1 ? '1.1.0' : '1.0.0', latest_attempt: attempts ? attempts === 1 ? failed : succeeded : null })
    }).as('adapter')
    cy.intercept('POST', '**/api/v1/adapters/example-adapter/update', (request) => {
      attempts += 1
      request.reply({ delay: 300, body: attempts === 1 ? failed : succeeded })
    }).as('update')
    cy.visit('/adapters/example-adapter')
    cy.wait('@adapter')
    cy.contains('button', /^Update$/).parent().within(() => cy.contains('button', 'Delete adapter').should('be.visible'))
    cy.contains('button', /^Update$/).click()
    cy.contains('PROCESSING').should('be.visible')
    cy.contains('button', 'Updating...').should('be.disabled')
    cy.contains('button', 'Delete adapter').should('be.disabled')
    cy.wait('@update')
    cy.contains('Latest attempt:').parent().should('contain', 'FAILED')
    cy.contains('Published version:').parent().should('contain', '1.0.0')
    cy.contains('Previous metadata retained.').should('be.visible')
    cy.contains('button', 'Retry registration').should('not.exist')
    cy.reload()
    cy.wait('@adapter')
    cy.contains('Latest attempt:').parent().should('contain', 'FAILED')
    cy.contains('button', /^Update$/).click()
    cy.wait('@update')
    cy.wait('@adapter')
    cy.contains('Latest attempt:').parent().should('contain', 'SUCCEEDED')
    cy.contains('Published version:').parent().should('contain', '1.1.0')
  })

  it('hides management actions when the backend denies ownership', () => {
    cy.intercept('GET', '**/api/v1/adapters/example-adapter', { body: { ...adapter, can_delete: false, can_update: false } })
    cy.visit('/adapters/example-adapter')
    cy.contains('Example Adapter').should('be.visible')
    cy.contains('button', /^Update$/).should('not.exist')
    cy.contains('button', 'Delete adapter').should('not.exist')
  })
})
