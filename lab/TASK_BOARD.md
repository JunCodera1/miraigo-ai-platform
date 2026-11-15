# Task Board (AI platform)
TODO | NEXT | DOING | DONE | BLOCKED

| ID | Việc | Ưu tiên | Trạng thái | Xong khi |
|---|---|---|---|---|
| A1–A6 | Nghiên cứu, nền tảng, ASR + stream, phân tích tiếng Nhật, phát âm v0, client Expo/Flutter | P0 | DONE | xem CURRENT_STATE |
| A7 | Kiểm token hợp lệ thật với backend | P0 | NEXT (user) | `curl -H "Authorization: Bearer $TOKEN" localhost:8090/api/v1/models` → 200 |
| A8 | Duyệt giấy phép SenseVoice (FunASR v1.1) | P0 | NEXT (user) | D-012 cập nhật |
| A16 | Push repo lên GitHub private | P0 | BLOCKED: `gh` token hết hạn | `git push -u origin main` OK |
| A9 | ~100 clip người học (có đồng ý) + nhãn → đo độ nhạy chấm phát âm | P1 | TODO | E-00x |
| A10 | LLM: sửa ngữ pháp + giải thích (adapter Anthropic/OpenAI-compatible, bộ eval) | P1 | TODO (cần API key) | eval chạy |
| A11 | Phát âm v1: GOP phoneme CTC + thời lượng mora | P1 | TODO | đo trên A9 |
| A14 | Tích hợp vào app (INTEGRATION_ROADMAP I-3, I-4) | P1 | TODO (cần duyệt, sửa repo app) | màn luyện phát âm trên emulator |
| A12 | Đánh giá Qwen3-ASR-0.6B, Whisper turbo (GPU) cho media dài | P2 | TODO | E-00x |
| A13 | Job queue cho video dài + sinh từ vựng/bài tập | P2 | TODO | — |
| A15 | Load test; rate limit bằng Redis khi >1 replica | P2 | TODO | — |
| A17 | CI (GitHub Actions: ruff + pytest không cần model) | P2 | DOING: `.github/workflows/ci.yml` viết xong, chưa chạy trên GitHub | workflow xanh |
