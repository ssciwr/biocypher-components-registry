# The frontend
The frontend is a simple React application that uses openapi-ts functions from the backend server to show, save and update information on Biocypher adapters.

Frontend ---> Openapi-ts --> Backend <---> Postgres (Data, stored in typed Columns)

e.g. Full toolchain example:
User visits home page --> User searches "Ope" --> Openapi-ts "searchForAdapter("Ope") --> Backend --> Postgres --> Backend --> Results[array: Adapters[{name: 'OpenTargets', ...}]] --> Frontend --> Frontend renders in AdapterPage

# Integration and deployment plan

## Already done/planned before
[x] - Have a dynamic, env set base URL and do not use hardcoded URLs (except external third party services with static URLs)

## Securing better integration:
[ ] - Add a Cypress test that confirms functionality of client-browser load with mocked API data (check a GET request is made to the backend for the adapter details of a single adapter, and that its description appears, and its returned DOI is looked up and provided as the citation count by the CrossRef API integration on the page)
[ ] - Add a way to mock or manually log in users for testing
[ ] - Add a Cypress test that checks if backend actually saves information once frontend triggers and update (e.g. endorsement)

## Deployment integration priorities
[ ] - We need the A record set up for the DNS so we can use/test out https containers docker configuration.
[ ] - We need to document docker compose commands for bringing up/down services via docker compose -f specified chosen files without removing the volumes (v) so we keep the data in postgres
[ ] - Agree on a date when we decide what data the backend will collect about adapters and from then onwards have a production build in use, and use migrations for all future changes.
[ ] - Document how to perform migrations via SSH (from which directory) to make future project updates
[ ] - Soon the MCP Workspace will need to be integrated too, need to research that.

## Manual testing in July 2026:
[ ] - Run manual test of the website and changing between pages
[ ] - Test adding adapter on slow 3G mode
[ ] - Manually Test loading and searching on mobile slow 3G mode

