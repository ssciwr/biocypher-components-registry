# The frontend
The frontend is a simple React application that uses generated `@hey-api/openapi-ts` functions from the backend server to show, save and update information on BioCypher adapters.

Frontend ---> `@hey-api/openapi-ts` client ---> FastAPI backend <---> Postgres

e.g. Full tool chain example for the adapter list:

1. User visits `/adapters`.
2. `AdaptersPage` renders `AdapterListView`.
3. `listLatestAdaptersApiV1AdaptersLatestGet()` calls `GET /api/v1/adapters/latest` using the configured `VITE_API_BASE_URL` backend base URL.
4. FastAPI `list_latest_adapters` returns up to 10000 newest canonical registry entries from Postgres through the registration store.
5. The backend returns `AdapterLatestListResponse` with `items: AdapterLatestItemResponse[]`.
6. The frontend stores those items as `LatestAdapter[]`.
7. Typing "Ope" in the search box calls `searchAdaptersApiV1AdaptersSearchGet({ query: { query: "Ope" } })`.
8. FastAPI `search_adapters` asks Postgres for adapter title matches and returns matching `AdapterLatestItemResponse` cards.
9. `AdapterListView` renders matching adapter cards with name, latest version, description, up to three keywords, maintainers, and endorsement count.

The generated client is rebuilt with:

```bash
pnpm run openapi-ts
```

# Integration and deployment plan

## Already done/planned before
[x] - Have a dynamic, env set base URL and do not use hardcoded URLs (except external third party services with static URLs)

## Securing better integration:
[x] - Add a Cypress test that confirms functionality of client-browser load with mocked API data (check a GET request is made to the backend for the adapter details of a single adapter, and that its description appears, and its returned DOI is looked up and provided as the citation count by the CrossRef API integration on the page)
[ ] - Add a way to mock or manually log in users for testing via their emails.
[ ] - Add a Cypress test that checks if backend actually saves information once frontend triggers and update (e.g. endorsement)

## Deployment integration priorities
[ ] - We need the A record set up for the DNS so we can use/test out https containers docker configuration.
[ ] - We need to document docker compose commands for bringing up/down services via docker compose -f specified chosen files without removing the volumes (v) so we keep the data in postgres
[ ] - Agree on a date when we decide what data the backend will collect about adapters and from then onwards have a production build in use, and use migrations for all future changes.
[ ] - Document how to perform migrations via SSH (from which directory) to make future project updates
[ ] - Soon the MCP Workspace will need to be integrated too, need to research that.

## Cross component reliably risks/areas:
We discovered at the BioCypher Workshop that some researchers are mandated to use their own insitutions instances to store source code (e.g. GitLab). Therefore, the backend needs to be able to parse at least Github and Gitlab urls for the repository croissant files and ideally, maintainer information (if possible)
[x] - I added a backend test and changed the backend parsing code and approach so for the gitlab/github difference, (A) the backend is the source of truth (B) its URL-parsing logic/system is used to verify whether the submitted repository url has a croissant file for feedback on the frontend, not duplicated code in the frontend.
Specific test:
for each of these urls:
[https://github.com/biocypher/collectri/, https://gitlab.com/gitlab-org/gitlab]
run the utility function _repository_url() to standardize it, then check:
AdapterMaintainerResponse can be extracted and from the web request:
(A) the adapter maintainer username is extracted
(B) the avatar url exists
(C) the avatar url returns 200

[ ] - Duplicated adapters can in theory be submitted by submitting both a master and main branch.
Based on the risk of people submitting adapters multiple times, I made it so we extract the repository url and then look up main/master only
(rather than supporting e.g. registering a "biocypher_ready_adapter" branch). However, users can still register using a "master" branch if "main" is already present.
We should write special code to prevent that and add a test.

## Types of test
### Performance tests
Current assessment: Not needed given our data is minimal. I checked the codebase and changed the search/latest listings to safe defaults for even very small VM resources (1GB of RAM etc)

### Static Verification
Improved by Linting, SonarQube and our Software Development Life Cycle/Gherkin docs

### Security Testing
Partially tested by SonarQube, we need to look at how we keep the most sensitive data (email for registration / Github information)
The Github token access should be reviewed

### Domain Review
We consulted with experts and adjusted the description we need, one minor feedback point was to use a dropdown for standard licenses rather than freetext for confident ease of use of the adapters

### Beta testing
We should plan a beta test once the croissant file generator part is implemented in the frontend

### User errors/issues:
We corrected search functionality behaviour (unclear system status in Nielens Usability terms) as it gave too little feedback.


## Manual testing in July 2026:
[ ] - Run manual test of the website and changing between pages
[ ] - Test adding adapter on slow 3G mode
[ ] - Manually Test loading and searching on mobile slow 3G mode
