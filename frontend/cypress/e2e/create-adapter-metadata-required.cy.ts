/*
Basic smoke test and frotnend html form input required validation confirmation - confirm step 1 can be completed and that saves to the local draft
Cover required first-step metadata fields and first creator draft commit.
*/
describe('Adapter metadata generator step 1 stage', () => {
  it('blocks step 1 until required fields and first creator are present', () => {
    cy.intercept('GET', '**/api/v1/auth/me', { statusCode: 401, body: { detail: 'GitHub sign-in required.' } }) // ignore
    cy.visit('/create/adapter-metadata?start=1', {
      onBeforeLoad(window) {
        window.localStorage.clear() // this is just to prevent issues with other tests/the local storage restore functionality.
      },
    })

    cy.contains('button', 'Continue').click()
    cy.contains('h2', 'Adapter details').should('be.visible')
    cy.get('input:invalid, textarea:invalid, select:invalid').should('have.length.greaterThan', 0)

    cy.contains('label', 'Adapter name').find('input').type('Required Test Adapter')
    cy.contains('label', 'Version').find('input').type('1.0.0')
    cy.contains('label', 'Repository URL').find('input').type('https://github.com/biocypher/test-adapter')
    cy.contains('label', 'License').find('select').select('MIT')
    cy.contains('label', 'Keywords').find('input').type('adapter, biocypher')
    cy.contains('label', 'Description').find('textarea').type('Creates metadata.')
    cy.contains('label', 'Name').find('input').type('Ada Lovelace')
    cy.contains('button', 'Continue').click()

    cy.contains('h2', 'Basic dataset info').should('be.visible')
    cy.window().its('localStorage').invoke('getItem', 'biocypher-adapter-metadata-draft')
      .then((draft) => {
        expect(JSON.parse(String(draft)).creators[0].name).to.equal('Ada Lovelace')
      })
  })
})
