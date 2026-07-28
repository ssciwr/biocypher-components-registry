# GitHub Sign-In Plan

Updated: 2026-05-29

## Goal

Add "Sign in with GitHub" to the React frontend and FastAPI backend without giving the app unnecessary GitHub permissions. For the first pass, authentication should establish the user's GitHub identity and local session only. Registry browsing stays public; submit/workspace routes can be gated after this is reviewed.

## Current Repo Fit

The backend is a FastAPI app assembled in `src/api/app.py` with routers under `src/api/routers/`. Settings are currently dataclass-based in `src/api/settings.py` and `src/core/settings.py`. Persistence uses shared SQLAlchemy table definitions in `src/persistence/tables.py`, with SQLite/PostgreSQL store implementations. There is no existing auth router, user table, session table, CORS setup, or cookie/session middleware.

The frontend can keep the sticky top bar and make the "Sign in with GitHub" button a normal link to the backend OAuth start endpoint:

```ts
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
```

```env
VITE_API_BASE_URL=http://localhost:8000
# When integrating, adjust this
```

## Recommended Flow

Use GitHub's OAuth web application flow:

1. Frontend sends the user to `GET /api/v1/auth/github/start`.
2. Backend creates a random `state`, stores a short-lived signed state cookie, and redirects to `https://github.com/login/oauth/authorize`.
3. GitHub redirects back to `GET /api/v1/auth/github/callback?code=...&state=...`.
4. Backend validates `state`, exchanges `code` for an access token at `https://github.com/login/oauth/access_token`, and requests JSON with `Accept: application/json`.
5. Backend fetches `https://api.github.com/user`.
6. Backend creates a local session and sets an HttpOnly cookie, then redirects to the frontend.
7. Frontend calls `GET /api/v1/auth/me` with credentials included to render signed-in state.

Scopes: use no extra scope or just `read:user`; the registration workflow uses the GitHub login and does not collect email.

## Backend Shape

Add `src/api/routers/auth.py`:

- `GET /auth/github/start`
- `GET /auth/github/callback`
- `GET /auth/me`
- `POST /auth/logout`

Add settings:

```env
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=
AUTH_SESSION_SECRET=
FRONTEND_BASE_URL=http://localhost:5175
VITE_API_BASE_URL=http://localhost:8000
BACKEND_BASE_URL=http://localhost:8000
# When integrating, adjust this
```

Use env-configured base URLs so local, staging, and production callback URLs do not get hardcoded into route code.

For sessions, prefer a database-backed table over putting GitHub data or access tokens in cookies:

- `auth_sessions(id_hash, github_user_id, github_login, github_email, avatar_url, created_at, expires_at, revoked_at)`
- Cookie stores only a random session token.
- DB stores only a hash of that token.
- Discard the GitHub access token after fetching identity unless a future feature explicitly needs GitHub API access.

Cookie defaults:

- `HttpOnly`
- `SameSite=Lax`, which supports the OAuth redirect back to the backend.
- `Secure=True` in production, `False` locally.
- Short expiry, e.g. 7 days, with logout revocation.

## Frontend Shape

Keep the top bar sticky. Change the sign-in link to:

```tsx
<a href={`${apiBaseUrl}/api/v1/auth/github/start`}>Sign in with GitHub</a>
```

After callback redirect, use a small `useEffect` in the app shell or auth provider to call `/api/v1/auth/me`. Any `fetch` call to authenticated backend routes should use:

```ts
credentials: 'include'
```

Do not wire access control into the three homepage action cards yet. They can remain `href="#"` until routes exist.

## Implementation Order

1. Add auth settings and `auth.py` router.
2. Add minimal session table and persistence functions for create/read/revoke.
3. Wire `auth.router` in `create_app()`.
4. Add GitHub OAuth start/callback endpoints with state validation.
5. Add `/auth/me` and `/auth/logout`.
6. Point frontend sign-in link at the backend start endpoint.
7. Add focused tests with mocked GitHub token/user responses.

## Risks / Decisions

- We need one GitHub OAuth App per deployed base URL, or the callback URL must exactly match each environment's backend callback route.
- If frontend and backend run on different hosts in production, CORS and cookie settings need explicit review.
- If registration submissions should be attributable, add `submitted_by_github_user_id` later rather than mixing auth changes into the first sign-in pass.
- If we need GitHub org/team authorization, that is a second feature using GitHub organization membership APIs and should not be bundled into basic sign-in.

## Sources

- GitHub OAuth web application flow: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps
- GitHub OAuth scopes: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps
- GitHub REST API authenticated user: https://docs.github.com/en/rest/users/users#get-the-authenticated-user
