const githubAvatarUrl = 'https://github.com/biocypher.png'
const missingAvatarUrl = '/missing-maintainer-avatar.png'

describe('Adapter maintainer avatar images', () => {
  it('renders GitHub avatars as normal browser images', () => {
    cy.request(githubAvatarUrl).its('status').should('eq', 200)
    cy.intercept('GET', '**/api/v1/auth/me', { statusCode: 401, body: { detail: 'GitHub sign-in required.' } })
    cy.intercept('GET', '**/api/v1/adapters/latest', { body: { items: [
      {
        adapter_id: 'github-adapter',
        adapter_name: 'GitHub Adapter',
        description: null,
        keywords: [],
        maintainer: { username: 'biocypher', avatar_url: missingAvatarUrl, profile_url: 'https://github.com/biocypher' },
        endorsement_count: 0,
        updated_at: '2026-07-06T00:00:00Z',
      },
    ] } })
    cy.visit('/adapters')

    cy.get('img[alt="biocypher"]').should('have.attr', 'src', missingAvatarUrl)
    cy.get('img[alt="biocypher"]').should('not.have.attr', 'crossorigin')
    cy.get('img[alt="biocypher"]').should(($avatar) => expect(($avatar[0] as HTMLImageElement).naturalWidth).to.equal(0))

    cy.intercept('GET', '**/api/v1/adapters/latest', { body: { items: [
      {
        adapter_id: 'github-adapter',
        adapter_name: 'GitHub Adapter',
        description: null,
        keywords: [],
        maintainer: { username: 'biocypher', avatar_url: githubAvatarUrl, profile_url: 'https://github.com/biocypher' },
        endorsement_count: 0,
        updated_at: '2026-07-06T00:00:00Z',
      },
    ] } })
    cy.visit('/adapters')

    cy.get('img[alt="biocypher"]').should('have.attr', 'src', githubAvatarUrl)
    cy.get('img[alt="biocypher"]').should('not.have.attr', 'crossorigin')
    cy.get('img[alt="biocypher"]').should(($avatar) => expect(($avatar[0] as HTMLImageElement).naturalWidth).to.be.greaterThan(0))
  })
})
