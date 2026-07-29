# The frontend
The frontend is a simple React application that uses generated `@hey-api/openapi-ts` functions it can import in JS - which are generated automatically from backned endpoints - to show, save and update information on BioCypher adapters.

Frontend ---> `@hey-api/openapi-ts` client ---> FastAPI backend <---> Postgres

## Example of how requests map between our components:
Full tool chain example for the adapter list:

1. User visits `/adapters`.
2. `AdaptersPage` renders `AdapterListView`.
3. `listLatestAdaptersApiV1AdaptersLatestGet()` calls `GET /api/v1/adapters/latest` using the configured `VITE_API_BASE_URL` backend base URL.
4. FastAPI `list_latest_adapters` returns up to 10000 newest canonical registry entries from Postgres through the registration store.
5. The backend returns `AdapterLatestListResponse` with `items: AdapterLatestItemResponse[]`.
6. The frontend stores those items as `LatestAdapter[]`.
7. Typing "Ope" in the search box calls `searchAdaptersApiV1AdaptersSearchGet({ query: { query: "Ope" } })`.
8. FastAPI `search_adapters` asks Postgres for adapter title matches and returns matching `AdapterLatestItemResponse` cards.
9. `AdapterListView` renders matching adapter cards with name, latest version, description, up to three keywords, maintainer, and endorsement count.

# Local development advice
I recommend to run the frontend with `pnpm run dev` and to run the backend using `uv` concurrently for local dev. That will use SQLite for the DB.

When you make updates to the backend which frontend needs to see (changing parameters), rerun this command which regenerates the functions. Then after that, import those functions in the frontend:
`pnpm run openapi-ts`

OpenAPI-ts just provides javascript(ts/typescript technically) functions you can call easily that run what your API provides.


# How to deploy
## 1. Build and tag relevant changed images locally for services that have changed

e.g. if only the frontend changed, you only need to build/retag the frontend version to a higher version:

## 2. Push images to GitHub Container Registry (GHCR)
- This requires that you have created a GHCR token for the project and logged in to the container registry via `docker login`


After this, the images should be on GHCR.

## 3. SSH into the remote, and then manually pull the updated images
`docker compose -f pr`

If pull fails, check if your GHCR token is up to date on both the instance and locally, and that you pushed successfully

# Integration and deployment plan

## Integration deliberate design/decisions
[x] - Have a dynamic, env set base URL and do not use hardcoded URLs (except external third party services with static URLs)
- Test ground/basic actions (e.g. backend call, taking action, results change upon interaction)
- For major user stories, add an integration test before full HTTPS integration, which should pass with HTTPS integration:
  - 1) A user can register an adapter with a github URL, the details are successfully fetched including avatar picture cross ref citation count.
  - 2) A user can generate a croissant file (which uses croissant baker under the hood) via providing manually the data sample and fields. When they update a specific field (e.g. a description), that is saved and seen in the generated croissant file
  - 3) A user can endorse an adapter, and after that the endorsement count increases
[x] to use GHCR images for the production builds
[x] to run on HeiCloud (instance already created and set up until docker-compose stage by Inga)
[x] not to automatically pull new images every night with a watcher (instead manual updates of the docker images are preferred as described in the "How to Deploy" above)

## Decisions to make
[ ] - How to mock backend for Cypress/full integration tests (SQLlite DB and run backend concurrently? That limits performance testing but as assessed below that is not a testing goal for this application)
[ ] - How to mock authentication/login for those tests(probably write mock code)

## Smoke testing key inter-service calls/actions:

[x] - Add a Cypress test that confirms functionality of client-browser load with mocked API data (check a GET request is made to the backend for the adapter details of a single adapter, and that its description appears, and its returned DOI is looked up and provided as the citation count by the CrossRef API integration on the page)
[ ] - Add a way in Cypress to mock or manually log in users for testing via their emails.
[ ] - Add a Cypress test that checks if backend actually saves information once frontend triggers and update (e.g. endorsement)
[x] - Add an adapter test which tests calling the API to endorse an adapter (A) increases the endorsement count by 1 (B) for the given mocked user shows that they themselves have endorsed it

## Deployment integration priorities
[ ] - We need the A record set up for the DNS so we can use/test out https containers docker configuration.
[ ] - We need to improve the GHCR management and document the process for images/what tagging system we will use (how to tag, push, how to update from a specific tag on production, which branches you should build images for (--> soon, only main))
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
AdapterMaintainerResponse can be extracted from the repository URL:
(A) the adapter maintainer username is extracted
(B) GitHub gets a deterministic avatar URL
(C) GitLab/institutional/self-hosted repositories keep the owner profile URL and the frontend renders an initials fallback when no avatar URL is available

## Server management
Until official release, the instance running on the server should be kept down with docker compose outside of testing windows (e.g. the Workshop),
but it can also be taken down without the "-v" option so that the volumes remain (so: use docker-compose -f <file> down") without the -v flag for removing volumes,
unless the volumes/existing adapters and data needs to be overwritten when a new data model comes out.

## Getting the repository to a useful state
We need to make sure we kickstart the repository manually which means having a number of adapters with croissant files which are useful.
(and possibly also the sample knowledge graph output from running create_knowledge_graph.py in the backend part)
We should probably seed 5-10 adapters manually so we have some existing content and that encourages other people to add their Adapters too.

## Types of test
### Performance tests
Current assessment: Not needed given our data is minimal. I checked the codebase and changed the search/latest listings to safe defaults for even very small VM resources (1GB of RAM etc)

### Static Verification
Improved by Linting, SonarQube and our Software Development Life Cycle/Gherkin docs

### Rate-limits decision
We should analyze the backend to add rate limits to more costly actions to run and prevent users using our API to process data.

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

## Use of AI
### For tests and integration
- I (James) use AI for creating backend tests and for fixing Cypress tests
- 50% of the time I outline the test cases and the process I want each to follow and then ask the AI to develop the test, to fail first.
- I do check the mock data/input data which is used and always ask: Is mocking and testing against this useful? Is the example relevant?

- I plan frontend tests/integration well upfront more in terms of user stories and see that as where testing can be completed mainly
- The docker compose file and env set up with BASE_URLS should be kept as is with no more complexity from AI.

### For documentation
- This documentation is 100% handwritten, except the full tool chain example, which I use AI to keep up to date with any changes.
- Comment documentation can be AI-written, but I either edit comments to be more accurate, rewrite them, or write them myself in functions to clarify thought process as I manually write code or annotate AI code
- I prohibit AI from adding todos and add those manually

### For frontend main UI elements
- I use AI to generate components in React with use tailwind classes, since that can finnicky
- However, I design and iterate on the fine parts of the choices/position both before and after using AI
- I make choices like whether the AdapterPage should have a separate view for a single adapter or that should be a separate page/component

### For backend code
- I try to avoid editing it too much as I focus on the frontend, so I mostly edit it when it makes sense to e.g. have a clear decision that the backend should be the soruce of truth (e.g. the Croissant meta file existence check for a given repository url)
- I tend to write a pseudo-code style algorithm or speicfy e.g. properties that need to be saved
- I check and review the schema and make sure AI adds a comment to each AI function; I remove that once I have read the function. I work to simplify anything which seems overly done.
- I check what existing tests are present and if those seem AI generated or not. I lean towards creating new test files, if something seems like it should be tested
