# Client integration

The platform is a separate service. Clients call it directly with the learner's backend access token;
the backend does not proxy. Base URL is configuration (e.g. `EXPO_PUBLIC_AI_BASE_URL`).

## Expo app (miraigo-x-p) — the real client today

[`examples/expo/ai-client.ts`](../examples/expo/ai-client.ts) is a drop-in module (only needs `zod`).
It type-checks inside the app's own `tsconfig` (`npx tsc --noEmit`) and was executed under Node 26
against a running server (analyze, WebM `Blob` upload, pronunciation, 422 error, 401 → one refresh).
Not yet run inside the Expo app on a device (that is step I-3/I-4, which changes the app).

Why a separate client and not the app's `api-client.ts`: that client always JSON-encodes bodies,
and the speech endpoints take `multipart/form-data`. Errors and the envelope are the same, so
`AiError` mirrors `ApiError`.

Suggested wiring (not applied to the app):

```ts
// src/integrations/ai/ai.ts
import { createAiClient } from './ai-client';
import { api } from '@/integrations/api/api-client';
import { authStorage } from '@/integrations/auth/auth-storage';

export const ai = createAiClient({
  baseUrl: process.env.EXPO_PUBLIC_AI_BASE_URL ?? 'http://localhost:8090',
  getAccessToken: authStorage.getAccessToken,
  // Any backend call through `api` refreshes a stale token (single-flight); then re-read it.
  refreshAccessToken: async () => {
    try { await api.get('/api/v1/users/me'); } catch { return null; }
    return authStorage.getAccessToken();
  },
});

// usage in a React Query mutation
const result = await ai.evaluatePronunciation(
  { uri: recording.uri, name: 'take.m4a', type: 'audio/mp4' },   // native (expo-audio)
  '東京に行きました',
);
```

On web pass the `Blob` from `MediaRecorder` (WebM/Opus is accepted). On the Android emulator add
`adb reverse tcp:8090 tcp:8090`, as for the backend. Add the web dev origin to
`JAI_CORS_ALLOWED_ORIGINS` (default already includes `http://localhost:8081`).

UI notes from the measurements: show `overall ≥ 90` as good; show per-word `issues[].message`; always
surface `limitations` once (e.g. an info icon): pitch accent is not assessed.

## Flutter

[`examples/flutter`](../examples/flutter) is a pure-Dart package (`package:http`), so it works in
Flutter on all platforms. Verified against a live server: `dart analyze` clean, and
`dart run bin/smoke.dart http://127.0.0.1:8091 clip.webm "参照"` analysed text, transcribed, scored
pronunciation and surfaced a typed error; against the auth-enforcing instance with a bad token it
raised `AiException(401 AI_AUTH_INVALID)`.

```dart
final ai = MiraigoAiClient(
  baseUrl: 'http://10.0.2.2:8090',            // Android emulator → host
  getAccessToken: () => secureStorage.read(key: 'access-token'),
  refreshAccessToken: authRepository.refresh,  // your backend refresh, returns new token or null
);
final result = await ai.evaluatePronunciation(bytes, 'take.m4a', '東京に行きました');
```

## Web app

Same contract as the Expo web build: `fetch` + `FormData`, `Authorization: Bearer`. Its origin must be
listed in `JAI_CORS_ALLOWED_ORIGINS`. The web app keeps its refresh token in an HttpOnly cookie
scoped to `/api/v1/auth` on the backend, so on 401 it refreshes against the backend and retries.

## Versioning

Breaking changes go to `/api/v2`; within v1 only additive changes (new optional fields/endpoints).
Clients should ignore unknown fields (the zod schemas above strip them).
