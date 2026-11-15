# Error codes

Stable, part of the contract. Clients should branch on `errorCode`, not on `message`.

| HTTP | `errorCode` | Meaning | Client action |
|---|---|---|---|
| 400 | `AI_BAD_REQUEST` | malformed request | fix request |
| 400 | `AI_AUDIO_INVALID` | not a readable audio/video file, no audio track, unsupported container | ask for another recording |
| 400 / 422 | `AI_AUDIO_EMPTY` | empty upload, too short (< 0.1 s), or silence (pronunciation) | re-record |
| 401 | `AI_AUTH_REQUIRED` | no/malformed `Authorization` header | sign in |
| 401 | `AI_AUTH_INVALID` | token rejected by the backend, or bad API key | refresh token via backend, retry once, else sign out |
| 403 | `AI_FORBIDDEN` | authenticated but not allowed | — |
| 404 | `AI_NOT_FOUND` | unknown route | — |
| 404 | `AI_MODEL_NOT_FOUND` | `model` field names an unknown or disabled model | drop `model` |
| 405 | `AI_METHOD_NOT_ALLOWED` | wrong HTTP method | — |
| 413 | `AI_FILE_TOO_LARGE` | upload above `JAI_MAX_UPLOAD_MB` | compress/shorten |
| 413 | `AI_AUDIO_TOO_LONG` | duration above the endpoint limit (120 s / 30 s) | shorten |
| 422 | `AI_VALIDATION_FAILED` | field validation; `errors` lists `{field, message}` | fix input |
| 422 | `AI_TEXT_NOT_JAPANESE` | reference text has nothing readable as Japanese | — |
| 429 | `AI_RATE_LIMITED` | per-user limit hit; `Retry-After` header | wait |
| 503 | `AI_BUSY` | all inference slots busy beyond queue timeout; `Retry-After` | retry later |
| 503 | `AI_PROVIDER_UNAVAILABLE` | no model in the chain could serve the request | retry later |
| 503 | `AI_AUTH_UNAVAILABLE` | backend unreachable for token check | retry later |
| 504 | `AI_PROVIDER_TIMEOUT` | every attempt timed out | retry later |
| 500 | `AI_INTERNAL_ERROR` | bug; quote `requestId` | report |

Outside production, 503/504 from the router include `errors: [{model, error}]` listing each attempt.
