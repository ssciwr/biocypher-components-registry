describe('MCP workspace page tests', () => {
  it('User must be logged in to create MCP sessions', () => {
    cy.intercept('GET', '**/api/v1/auth/me', { statusCode: 401, body: { detail: 'GitHub sign-in required.' } })
    cy.visit('/workspace')
    cy.get('dialog[aria-label="Sign in to use the MCP Workspace"]').should('be.visible')
    cy.contains('a', 'Sign in with GitHub').should('have.attr', 'href').and('include', '/api/v1/auth/github/start')
    cy.contains('and provide a Claude API key to use the MCP Workspace').should('be.visible')
  })

  it('Workspace session starts after sign in', () => {
    cy.intercept('GET', '**/api/v1/auth/me', { body: { authenticated: true } }) // fake login the user

    // Mock workspace APIs:
    cy.intercept('POST', '**/agent/api/v1/sessions', { statusCode: 201, body: { session_id: 'session-1', session_token: 'token-1', tools: [{ name: 'write_file' }] } })
    cy.intercept('GET', '**/agent/api/v1/sessions/session-1/events', { headers: { 'content-type': 'text/event-stream' }, body: 'event: session_state\ndata: {"has_key": false, "busy": false, "error": null}\n\nevent: text_delta\ndata: {"text":"\\n\\n## MCP summary\\n\\n- write files"}\n\n' })
    cy.intercept('POST', '**/agent/api/v1/sessions/session-1/key', { statusCode: 204 }).as('attachKey')

    // User action...
    cy.visit('/workspace').then(() => cy.contains('button', 'Start workspace').click())
    cy.get('dialog[aria-label="Provide Anthropic API key"]').should('be.visible')
    cy.get('input[placeholder="sk-ant-..."]').type('sk-ant-test-key')
    cy.contains('button', 'Attach key').click()
    cy.wait('@attachKey').its('request.body').should('deep.equal', { api_key: 'sk-ant-test-key' })
    cy.get('dialog[aria-label="Provide Anthropic API key"]').should('not.exist')

    // UI now displays
    cy.contains('ready').should('be.visible')
    cy.contains('h2', 'MCP summary').should('be.visible')
  })

  it('Agent file changes refresh the file tree in the background', () => {
    cy.intercept('GET', '**/api/v1/auth/me', { body: { authenticated: true } })
    cy.intercept('POST', '**/agent/api/v1/sessions', { statusCode: 201, body: { session_id: 'session-1', session_token: 'token-1', tools: [] } })
    // A burst of fs_changed events, as after a reconnect replay.
    const fsChanged = [1, 2, 3].map((id) => `event: fs_changed\nid: ${id}\ndata: {"paths": ["adapter.py"]}\n\n`).join('')
    cy.intercept('GET', '**/agent/api/v1/sessions/session-1/events', { headers: { 'content-type': 'text/event-stream' }, body: `event: session_state\ndata: {"has_key": true, "busy": false, "error": null}\n\n${fsChanged}` })
    let listed = 0
    cy.intercept('GET', '**/agent/api/v1/sessions/session-1/files*', (request) => {
      listed += 1
      request.reply({
        body: {
          path: '',
          entries: listed === 1 ? [] : [{ name: 'adapter.py', path: 'adapter.py', is_dir: false }],
        },
      })
    }).as('files')

    cy.visit('/workspace').then(() => cy.contains('button', 'Start workspace').click())

    cy.contains('adapter.py').should('be.visible')
    // Initial load plus reloads; the three events collapse to at most two.
    cy.wait(500).then(() => expect(listed).to.be.within(2, 3))
  })
})
