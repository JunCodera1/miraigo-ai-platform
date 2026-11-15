# Integration Roadmap (AI platform ↔ apps)

| Step | What | Who/where | Done when |
|---|---|---|---|
| I-1 | Run platform locally next to backend (`:8090`) | dev | `/health/ready` ok — DONE 2026-11-14 |
| I-2 | Valid-token check against real backend | user runs `curl -H "Authorization: Bearer $TOKEN" localhost:8090/api/v1/models` | 200 with model list |
| I-3 | Copy `examples/expo/ai-client.ts` into app, add `EXPO_PUBLIC_AI_BASE_URL` | APP (needs approval: changes app) | typecheck clean |
| I-4 | First screen: pronunciation practice on grammar examples (`sentenceJp` + `audioUrl` already in BE) | APP | record → score → per-word issues on emulator |
| I-5 | Furigana/reading toggle using `/language/analyze` on lesson/grammar text | APP | |
| I-6 | Deploy: compose service next to backend on EC2, reverse proxy `/ai/` with WebSocket upgrade | ops | prod `/health/ready` |
| I-7 | Persist pronunciation results for personalisation (BE table or AI DB) | decision | D-entry recorded |
| I-8 | LLM features (grammar correction, explanations) | platform | eval set + API key |

Rules: the app is not changed without approval (I-3/I-4); the backend is a shared repo that deploys on
push — no BE change is needed for I-1..I-6.
