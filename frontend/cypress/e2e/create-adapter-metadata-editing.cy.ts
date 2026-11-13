/// <reference types="cypress" />

const generatedDatasetMetadata = {
  '@type': 'sc:Dataset',
  name: 'People Dataset',
  description: 'Small people dataset.',
  license: 'MIT',
  version: '0.0.1',
  datePublished: '2026-04-17',
  distribution: [{ '@type': 'cr:FileObject', contentUrl: 'https://example.org/people.csv', name: 'people.csv' }],
  recordSet: [{ '@type': 'cr:RecordSet', name: 'People records', field: [] }],
}

const uploadedDatasetMetadata = {
  '@type': 'sc:Dataset',
  name: 'Uploaded Dataset',
  description: 'Uploaded dataset.',
  license: 'MIT',
  version: '0.0.1',
  datePublished: '2026-04-17',
  creator: {
    '@type': 'sc:Person',
    image: 'https://example.org/creator.png',
    name: 'Uploaded Creator',
  },
  distribution: [{ '@type': 'cr:FileObject', contentUrl: 'https://example.org/uploaded.csv', name: 'uploaded.csv' }],
  recordSet: [{ '@type': 'cr:RecordSet', name: 'Uploaded records', field: [] }],
}

/*
 * AI-Generated.
 */
function visitGenerator() {
  cy.intercept('GET', '**/api/v1/auth/me', { statusCode: 401, body: { detail: 'GitHub sign-in required.' } })
  cy.visit('/create/adapter-metadata?start=1', {
    onBeforeLoad(window: Window) {
      window.localStorage.clear()
    },
  })
}

function interceptDatasetGeneration() {
  cy.intercept('POST', '**/api/v1/metadata/upload-sessions', {
    statusCode: 201,
    body: {
      session_id: 'dataset-upload-session',
      token: 'dataset-upload-token',
      max_artifact_bytes: 1 * 1024 * 1024,
      expires_in_seconds: 1800,
    },
  }).as('createUploadSession')
  cy.intercept('PUT', '**/api/v1/metadata/upload-sessions/dataset-upload-session/artifacts/*', {
    body: {
      entry_id: 'entry-1',
      artifact_size: 16,
      artifact_sha256: '0'.repeat(64),
      complete_entries: 1,
      total_entries: 1,
    },
  }).as('uploadArtifact')
  cy.intercept('POST', '**/api/v1/metadata/upload-sessions/dataset-upload-session/finalize', {
    statusCode: 202,
    body: { status: 'processing' },
  }).as('generateDataset')
  cy.intercept('GET', '**/api/v1/metadata/upload-sessions/dataset-upload-session', {
    body: {
      status: 'complete',
      next_poll_ms: 1000,
      result: { metadata: generatedDatasetMetadata, warnings: [] },
    },
  }).as('datasetGenerationStatus')
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
 * AI-Generated - then human-modified
 */
function editDatasetRow(name: string) {
  getDatasetRow(name).within(() => {
    cy.contains('button', 'Edit').click()
  })
}

function getDatasetRow(name: string) {
  return cy.get(`td[title="${name}"]`).closest('tr')
}

function expectDatasetMetadataSection(name: string) {
  cy.contains('h2', 'Dataset details').should('be.visible')
  cy.get('#dataset-metadata-section').within(() => {
    cy.contains('h3', 'Dataset metadata').should('be.visible')
    cy.contains('label', 'Dataset name').find('input').should('have.value', name)
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
  it('does not offer resume until a previous session contains user input', () => {
    cy.visit('/create', {
      onBeforeLoad(window) {
        window.localStorage.clear()
      },
    })
    cy.contains('h2', 'Resume previous session').should('not.exist')
  })

  it('starting from scratch discards a previous saved session', () => {
    visitGenerator()
    cy.contains('label', 'Adapter name').find('input').type('Discarded Adapter')
    cy.visit('/create')
    cy.contains('a', 'Start from scratch').click()
    cy.contains('label', 'Adapter name').find('input').should('have.value', '')
    cy.window().its('localStorage').invoke('getItem', 'biocypher-adapter-metadata-draft').should('be.null')
  })

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

  it('resumes a saved metadata session', () => {
    visitGenerator()
    cy.contains('label', 'Adapter name').find('input').type('Resumable Adapter')

    cy.visit('/create')
    cy.contains('h2', 'Resume previous session').should('be.visible')
    cy.contains('a', 'Resume session').click()

    cy.location('search').should('equal', '?resume=1')
    cy.contains('label', 'Adapter name').find('input').should('have.value', 'Resumable Adapter')
  })

  it('offers file and folder selection from one source button', () => {
    visitGenerator()
    fillAdapterStep()

    cy.contains('button', 'Browse source').click()
    cy.get('[role="menu"][aria-label="Dataset source type"]').within(() => {
      cy.contains('button', 'Select one file').should('be.visible')
      cy.contains('button', 'Select one folder').should('be.visible')
    })

    cy.window().then((window) => {
      const first = new window.File(['id,name\n1,Alice\n'], 'first.csv', { type: 'text/csv' })
      const second = new window.File(['id,name\n2,Bob\n'], 'second.csv', { type: 'text/csv' })
      Object.defineProperty(first, 'webkitRelativePath', { value: 'people/first.csv' })
      Object.defineProperty(second, 'webkitRelativePath', { value: 'people/second.csv' })
      const transfer = new window.DataTransfer()
      transfer.items.add(first)
      transfer.items.add(second)

      cy.get('input[aria-label="Source dataset folder"]').then(($input) => {
        Object.defineProperty($input[0], 'files', { configurable: true, value: transfer.files })
        $input[0].dispatchEvent(new window.Event('change', { bubbles: true }))
      })
    })

    cy.contains('people (2 files)').should('be.visible')
  })

  it('keeps dataset creators after dataset details edit', () => {
    interceptDatasetGeneration()
    cy.intercept('POST', '**/api/v1/metadata/adapters/generate', { body: { metadata: { '@type': 'SoftwareSourceCode' } } }).as('generateAdapter')
    visitGenerator()
    fillAdapterStep()
    cy.get('input[aria-label="Source dataset file"]').selectFile({
      contents: Cypress.Buffer.from('id,name\n1,Alice\n'),
      fileName: 'people.csv',
      mimeType: 'text/csv',
    }, { force: true })
    cy.contains('label', 'Dataset name').find('input').type('People Dataset')
    cy.contains('label', 'Dataset version').find('input').type('0.0.1')
    cy.contains('label', 'Date published').find('input').type('2026-04-17')
    cy.contains('label', 'Dataset download URL').find('input').type('https://example.org/people.csv')
    addCreator('Dataset creators', 'Dataset Creator A')
    addCreator('Dataset creators', 'Dataset Creator B')
    cy.contains('button', 'Add dataset details').click()
    cy.wait('@createUploadSession')
    cy.wait('@uploadArtifact')
    cy.wait('@generateDataset')
    cy.wait('@datasetGenerationStatus')
    expectDatasetMetadataSection('People Dataset')
    cy.contains('label', 'Dataset name').find('input').clear().type('People Dataset Edited')
    cy.contains('button', 'Save this dataset').click()
    getDatasetRow('People Dataset Edited').should('be.visible')
    cy.contains('button', 'Generate adapter Croissant file').click()
    cy.wait('@generateAdapter').then(({ request }) => {
      const dataset = request.body.dataset_documents[0]
      expect(dataset.name).to.equal('People Dataset Edited')
      expect(dataset.version).to.equal('0.0.1')
      expect(dataset.datePublished).to.equal('2026-04-17T00:00:00Z')
      expect(dataset.creator).to.have.length(2)
      expect(dataset.creator[0].name).to.equal('Dataset Creator A')
    })
  })

  it('keeps an uploaded dataset available for editing after returning to the dataset list', () => {
    visitGenerator()
    fillAdapterStep()
    addUploadedDataset()
    cy.contains('h2', 'Dataset details').should('be.visible')
    cy.contains('button', 'Save this dataset').click()
    cy.contains('button', 'Add another dataset').click()
    editDatasetRow('Uploaded Dataset')
    cy.contains('h2', 'Dataset details').should('be.visible')
    cy.contains('h2', 'Basic dataset info').should('not.exist')
    cy.contains('button', 'Save this dataset').click()
    getDatasetRow('Uploaded Dataset').should('be.visible')
    cy.contains('button', 'Add another dataset').click()
    editDatasetRow('Uploaded Dataset')
    cy.contains('h2', 'Dataset details').should('be.visible')
    cy.contains('button', 'Save this dataset').should('be.visible')
  })

  it('edits an uploaded dataset creator from the dataset review', () => {
    visitGenerator()
    fillAdapterStep()
    addUploadedDataset()

    cy.contains('h3', 'Dataset creators').parent().within(() => {
      cy.contains('li', 'Uploaded Creator').contains('button', 'Edit').click()
      cy.contains('label', /^Name$/).find('input').clear().type('Edited Uploaded Creator')
      cy.contains('button', 'Save creator').click()
      cy.contains('li', 'Edited Uploaded Creator').should('be.visible')
      cy.contains('span', /^Uploaded Creator$/).should('not.exist')
    })
  })
})
