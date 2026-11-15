# Authentication

Clients send the **same access token they use for the MiraiGo backend**:
`Authorization: Bearer <token>`.

The platform does not verify the JWT itself. A backend token is valid only if its signature is right,
it is an *access* token (`token_type=ACCESS`) and its id is still present in the backend's Redis
(logout revokes it). Re-implementing that would mean sharing the JWT secret and Redis layout. So the
platform asks the backend: `GET {JAI_BACKEND_BASE_URL}/api/v1/users/me` with the caller's token
(lab decision D-009).

| Backend answer | Platform answer |
|---|---|
| 200 `{id, username, role}` | request proceeds; principal `user:<id>` |
| 401 / 403 | 401 `AI_AUTH_INVALID` (client should refresh via the backend and retry once) |
| unreachable / 5xx | 503 `AI_AUTH_UNAVAILABLE` — fails closed |

- Successful checks are cached for `JAI_AUTH_CACHE_TTL_SECONDS` (default 60, keyed by a SHA-256 of
  the token). A token revoked by logout keeps working here for at most that long; set 0 to disable.
- Missing/malformed header → 401 `AI_AUTH_REQUIRED` with `WWW-Authenticate: Bearer`.
- Server-to-server callers can use `X-API-Key` with a key from `JAI_SERVICE_API_KEYS`
  (constant-time comparison). Service principals may read `/api/v1/admin/usage`.
- WebSocket: the token goes in the first message, never in the URL ([STREAMING.md](STREAMING.md)).
- `JAI_AUTH_MODE=none` disables auth for local development and is rejected at startup when
  `JAI_ENV=production`.
- Rate limits (per principal, per process): `JAI_RATE_LIMIT_PER_MINUTE` overall,
  `JAI_INFERENCE_RATE_LIMIT_PER_MINUTE` for speech endpoints → 429 `AI_RATE_LIMITED` + `Retry-After`.

Verified live (2026-11-14) against the running backend: no token → 401 `AI_AUTH_REQUIRED`; garbage
token → backend 401 → platform 401 `AI_AUTH_INVALID`. A valid token was **not** exercised live (no
credentials available to the session); that path is covered by tests with a mocked backend. To check
it yourself: `curl -H "Authorization: Bearer $TOKEN" localhost:8090/api/v1/models`.
