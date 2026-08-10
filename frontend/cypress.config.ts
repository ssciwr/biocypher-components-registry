import { defineConfig } from 'cypress'

export default defineConfig({
  e2e: {
    baseUrl: 'http://localhost:5173',
    specPattern: 'cypress/e2e/**/*.cy.ts',
    supportFile: false, // manually added as we don't need it for now with just mocked backend anyhow.
  },
})

// due to this error:
/*
Your project does not contain a default supportFile. We expect a file matching cypress/support/e2e.{js,jsx,ts,tsx} to exist.

If a support file is not necessary for your project, set supportFile to false.

 */
