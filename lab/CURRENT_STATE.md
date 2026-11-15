# Current State (cập nhật 2026-11-15)

## Đã xong [V]
- Endpoint: `/speech/transcribe` (JSON/SRT/VTT), `WS /speech/stream`, `/pronunciation/evaluate` (mora v0, tuyến model riêng D-016), `/language/analyze`, `/models`, `/health/live|ready`, `/admin/usage`.
- 104 test pytest xanh (2 dùng model thật nếu có), ruff sạch, `docker compose up` với `.env.example` healthy (read-only, models `:ro`).
- Đo: E-001 ASR (SenseVoice 8.5 % CER), E-002 độ khắt khe chấm phát âm, E-003 kiểm tra sống — `EXPERIMENT_RESULTS.md`.
- Client Expo (`examples/expo/ai-client.ts`) chạy thật bằng Node + typecheck trong app; client Dart chạy thật.
- 2026-11-15: tách thành repo riêng (D-017), commit đầu trên `main`, chưa push.

## Chưa làm / chưa kiểm
Token hợp lệ thật (A7), LLM, TTS, pitch accent, giọng người học, tải đồng thời, GPU, triển khai EC2, CI.

## Môi trường
- Venv: `~/.local/share/japanese-ai-platform/venv` (Python 3.14, cài editable từ repo này). Model ~1.7 GB, FLEURS, báo cáo eval cũng ở đó.
- Chạy: `~/.local/share/japanese-ai-platform/venv/bin/japanese-ai` (cổng 8090). Backend MiraiGo: `../miraigo-be` qua Docker :8080.
- Container prototype cũ `miraigo-ai-server` (:8000) — không dừng, không prune (checkpoint LID chỉ có trong image).

## Bước kế
A16 (push, cần `gh auth login`), A7, A8 → A9/A10.
