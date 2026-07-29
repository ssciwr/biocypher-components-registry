const doi = '10.5555/12345678'
const draftKey = 'bcr-register-draft'
const submitAfterAuthKey = 'bcr-register-submit-after-auth'
const draft = {
  adapterName: 'Auto Submit Adapter',
  repositoryLocation: 'https://github.com/biocypher/auto-submit-adapter',
  licenseValue: 'MIT',
  doi,
  cffUrl: '',
}
const submittedRegistration = {
  adapter_id: 'auto-submit-adapter',
  adapter_name: draft.adapterName,
  created_at: '2026-07-29T12:00:00Z',
  license_value: draft.licenseValue,
  doi,
  cff_url: null,
  registration_id: 'registration-1',
  repository_kind: 'remote',
  repository_location: draft.repositoryLocation,
  status: 'SUBMITTED',
  submitted_by_github_login: 'jmsssc',
}

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


  it('auto submits the saved draft after GitHub sign-in returns', () => {
    cy.intercept('GET', '**/api/v1/auth/me', { body: { github_login: 'jmsssc' } })
    cy.intercept('GET', '**/api/v1/registrations/croissant-file-present-check*', { body: { has_croissant_file: true } })
    cy.intercept('POST', '**/api/v1/registrations', {
      body: submittedRegistration,
    }).as('createRegistration')
    cy.intercept('POST', '**/api/v1/registrations/registration-1/process', {
      body: {
        ...submittedRegistration,
        metadata: {},
        metadata_path: 'croissant.jsonld',
        profile_version: '1.0',
        status: 'VALID',
        uniqueness_key: 'auto-submit-adapter::1.0.0',
        updated_at: '2026-07-29T12:00:01Z',
        validation_errors: [],
      },
    }).as('processRegistration')

    cy.visit('/register', {
      onBeforeLoad(window) {
        window.localStorage.setItem(draftKey, JSON.stringify(draft))
        window.localStorage.setItem(submitAfterAuthKey, '1')
      },
    })
    cy.wait('@createRegistration').its('request.body').should('deep.include', {
      adapter_name: draft.adapterName,
      repository_location: draft.repositoryLocation,
      license_value: draft.licenseValue,
      doi,
    })
    cy.wait('@processRegistration')
    cy.contains('Adapter registration successful').should('be.visible')
    cy.window().its('localStorage').invoke('getItem', draftKey).should('equal', null)
    cy.window().its('localStorage').invoke('getItem', submitAfterAuthKey).should('equal', null)
  })
})
