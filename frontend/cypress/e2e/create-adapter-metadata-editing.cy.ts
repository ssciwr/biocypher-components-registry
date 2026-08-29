const generatedDatasetMetadata = {
  '@type': 'sc:Dataset',
  name: 'People Dataset',
  description: 'Small people dataset.',
  license: 'MIT',
  distribution: [{ '@type': 'cr:FileObject', contentUrl: 'https://example.org/people.csv', name: 'people.csv' }],
  recordSet: [{ '@type': 'cr:RecordSet', name: 'People records', field: [] }],
}

const uploadedDatasetMetadata = {
  '@type': 'sc:Dataset',
  name: 'Uploaded Dataset',
  description: 'Uploaded dataset.',
  license: 'MIT',
  distribution: [{ '@type': 'cr:FileObject', contentUrl: 'https://example.org/uploaded.csv', name: 'uploaded.csv' }],
  recordSet: [{ '@type': 'cr:RecordSet', name: 'Uploaded records', field: [] }],
}

/*
 * AI-Generated.
 */
function visitGenerator() {
  cy.intercept('GET', '**/api/v1/auth/me', { statusCode: 401, body: { detail: 'GitHub sign-in required.' } })
  cy.visit('/create/adapter-metadata?start=1', {
    onBeforeLoad(window) {
      window.localStorage.clear()
    },
  })
}

/*
 * AI-Generated.
 */
function addCreator(sectionTitle: string, name: string) {
  cy.contains('h3', sectionTitle).parent().within(() => {
    cy.contains('label', /^Name$/).find('input').clear().type(name)
    cy.contains('button', 'Add creator').click()
  })
}

/*
 * AI-Generated.
 */
function fillAdapterStep() {
  cy.contains('label', 'Adapter name').find('input').type('Edit Flow Adapter')
  cy.contains('label', 'Version').find('input').type('1.0.0')
  cy.contains('label', 'Repository URL').find('input').type('https://github.com/biocypher/edit-flow-adapter')
  cy.contains('label', 'License').find('select').select('MIT')
  cy.contains('label', 'Keywords').find('input').type('adapter, biocypher')
  cy.contains('label', 'Description').find('textarea').type('Creates metadata for edited datasets.')
  addCreator('Creators', 'Adapter Creator')
  cy.contains('button', 'Continue').click()
}

/*
 * AI-Generated.
 */
function editDatasetRow(name: string) {
  cy.contains('tr', name).within(() => {
    cy.contains('button', 'Edit').click()
  })
}

/*
 * AI-Generated.
 */
function addUploadedDataset() {
  cy.contains('button', 'Upload existing dataset Croissant file').click()
  cy.contains('label', 'Dataset Croissant file').find('input').selectFile({
    contents: Cypress.Buffer.from(JSON.stringify(uploadedDatasetMetadata)),
    fileName: 'uploaded.jsonld',
    mimeType: 'application/ld+json',
  })
  cy.contains('button', 'Add dataset').click()
}

describe('adapter metadata generator editing', () => {
  it('auto-populates adapter id from name', () => {
    visitGenerator()
    cy.contains('label', 'Adapter name').find('input').type('Human Protein Atlas Adapter')
    cy.contains('label', 'Adapter ID').find('input').should('have.value', 'human-protein-atlas-adapter')
    cy.contains('label', 'Adapter ID').find('input').clear().type('hpa-custom')
    cy.contains('label', 'Adapter name').find('input').type(' v2')
    cy.contains('label', 'Adapter ID').find('input').should('have.value', 'hpa-custom')
    cy.contains('label', 'Adapter name').find('input').should('have.value', 'Human Protein Atlas Adapter v2')
  })

  it('edits adapter creators in place', () => {
    visitGenerator()
    addCreator('Creators', 'Ada Lovelace')
    cy.contains('h3', 'Creators').parent().within(() => {
      cy.contains('li', 'Ada Lovelace').contains('button', 'Edit').click()
      cy.contains('label', /^Name$/).find('input').clear().type('Grace Hopper')
      cy.contains('button', 'Save creator').click()
      cy.contains('li', 'Grace Hopper').should('be.visible')
      cy.contains('li', 'Ada Lovelace').should('not.exist')
      cy.get('li').should('have.length', 1)
    })
  })

  it('keeps dataset creators after dataset details edit', () => {
    cy.intercept('POST', '**/api/v1/metadata/datasets/generate', { body: { metadata: generatedDatasetMetadata } }).as('generateDataset')
    cy.intercept('POST', '**/api/v1/metadata/adapters/generate', { body: { metadata: { '@type': 'SoftwareSourceCode' } } }).as('generateAdapter')
    visitGenerator()
    fillAdapterStep()
    cy.contains('label', 'Source dataset file').find('input').selectFile({
      contents: Cypress.Buffer.from('id,name\n1,Alice\n'),
      fileName: 'people.csv',
      mimeType: 'text/csv',
    })
    cy.contains('label', 'Dataset name').find('input').type('People Dataset')
    addCreator('Dataset creators', 'Dataset Creator A')
    addCreator('Dataset creators', 'Dataset Creator B')
    cy.contains('button', 'Add dataset').click()
    cy.wait('@generateDataset')
    cy.contains('label', 'Dataset name').find('input').clear().type('People Dataset Edited')
    cy.contains('button', 'Finish this stage').click()
    cy.wait('@generateAdapter').then(({ request }) => {
      const dataset = request.body.dataset_documents[0]
      expect(dataset.name).to.equal('People Dataset Edited')
      expect(dataset.creator).to.have.length(2)
      expect(dataset.creator[0].name).to.equal('Dataset Creator A')
    })
  })

  it('keeps dataset after edit then back then edit again', () => {
    visitGenerator()
    fillAdapterStep()
    addUploadedDataset()
    cy.contains('h2', 'Dataset details').should('be.visible')
    cy.contains('button', 'Back').click()
    editDatasetRow('Uploaded Dataset')
    cy.contains('button', 'Back').click()
    cy.contains('button', 'Continue').click()
    editDatasetRow('Uploaded Dataset')
    cy.contains('tr', 'Uploaded Dataset').should('be.visible')
    cy.contains('button', 'Save dataset').should('be.visible')
    cy.contains('No datasets added yet').should('not.exist')
  })
})
