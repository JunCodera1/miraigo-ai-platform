# Decisions (AI platform)

D-007, D-009..D-016 chép nguyên từ `miraigo-x-p/lab/DECISIONS.md` (giữ số cũ). Quyết định mới đánh số từ D-017.

## D-007 `japanese-ai-platform/` đặt ở gốc repo app (2026-11-12)
Master prompt yêu cầu thư mục ở "gốc repo hiện có", nhưng dự án có 2 repo. Chọn `miraigo-x-p` vì: `lab/` đã ở đây (D-001); `miraigo-be` là repo chung của nhóm và **tự deploy khi push main**; builder Docker classic của BE sẽ nén cả thư mục vào build context.
Hệ quả: tsconfig của app quét `**/*.ts`, eslint chỉ bỏ `dist/*`, Metro theo dõi cả cây → (a) venv, model, audio eval đặt **ngoài repo** (`~/.local/share/japanese-ai-platform/`); (b) ví dụ TS phải qua được typecheck/lint của app; (c) sau khi thêm file phải chạy lại `npm run typecheck && npm run lint && npm test`.
Thư mục không phụ thuộc đường dẫn: chuyển sang repo riêng chỉ cần `mv`.
Đã loại: gốc `miraigo-be` (lý do trên); thư mục anh em ngoài repo (trái yêu cầu).

## D-009 Nền tảng AI xác thực bằng introspection qua backend (2026-11-12)
Vấn đề [V]: token hợp lệ ở BE = chữ ký HS256 đúng **và** `token_type=ACCESS` **và** còn key Redis `auth:access:<jti>`. Chỉ kiểm chữ ký sẽ nhận cả refresh token lẫn token đã logout.
Chọn: gọi `GET {BACKEND}/api/v1/users/me` với Bearer token của client; 200 → lấy `{id, username, role}`; cache kết quả dương tính TTL ngắn (mặc định 60s, cấu hình được); BE không tới được → 503 (fail closed).
Ưu: không chia sẻ JWT secret, không phụ thuộc định dạng Redis của BE, có luôn user id. Nhược: thêm 1 hop khi cache trượt; token logout còn dùng được tối đa TTL.
Đã loại: tự kiểm JWT + Redis (nhân đôi logic BE, phải chia sẻ secret).

## D-010 Quy tắc an toàn bộ nhớ khi chạy model trên máy dev (2026-11-12)
RAM thường gần đầy, swap đầy, user mở ứng dụng desktop. Mọi lần nạp model chạy qua `scripts/run-capped.sh <MiB> …` (cgroup `MemoryMax`, `MemorySwapMax=0`, `oom_score_adj=1000`; đã thử: cấp 300 MiB dưới trần 128 MiB bị kill 137). Mỗi lần một model. Ưu tiên CTranslate2/ONNX, không cài torch. File lớn không để ở `/tmp` (tmpfs): dùng `TMPDIR=~/.local/share/japanese-ai-platform/tmp`. Ứng viên không chạy nổi thì ghi "not run: memory", không ngoại suy.

## D-011 Stack của nền tảng AI: Python 3.12+ / FastAPI, không torch (2026-11-14)
Hệ sinh thái model (ONNX Runtime, CTranslate2, Sudachi) là Python; async FastAPI đủ cho I/O, việc nặng chạy trong thread. Không cài torch (máy dev thiếu RAM, image nhỏ hơn): mọi model local chạy qua sherpa-onnx/CTranslate2. Đã loại: Java trong BE (thiếu thư viện), Node.

## D-012 ASR mặc định = SenseVoice Small int8, fallback ReazonSpeech → Parakeet → OpenAI (2026-11-14)
Bằng chứng E-001 (FLEURS ja, 100 câu, CPU): SenseVoice CER 8.5 %, RTF 0.023, 370 MB; Parakeet hòa CER nhưng chậm 2×, RAM 3×; ReazonSpeech 10.0 %, Apache-2.0, có timestamp token. Moonshine ja bị tắt (giấy phép phi thương mại). Rủi ro: giấy phép FunASR v1.1 là giấy phép riêng (ghi nguồn, giữ tên model, không nói rõ về thương mại) → **chủ dự án cần duyệt**; nếu không chấp nhận: `JAI_ASR_MODEL=reazonspeech-zipformer-ja` (không đổi code).

## D-013 Đánh giá phát âm v0 = so khớp mora từ kết quả ASR (2026-11-14)
Làm được ngay, giải thích được, đo được (E-002: người bản xứ đọc đúng → trung vị 96–99). Không chấm pitch accent; ASR có thể "sửa giùm" lỗi nhỏ. Kế tiếp: GOP từ model phoneme CTC (v1), F0 cho trọng âm (v2). Đã loại: Azure (ja-JP không có prosody, dữ liệu rời hệ thống).

## D-014 Envelope giống backend + `requestId`; client riêng cho multipart (2026-11-14)
App bóc `data` một kiểu cho cả hai dịch vụ. `api-client.ts` của app luôn JSON-encode body nên client AI là module riêng (`examples/expo/ai-client.ts`), cùng quy ước lỗi.

## D-015 Không lưu dữ liệu người học trong nền tảng AI (2026-11-14)
File tải lên → file tạm 0600 → xóa ngay sau khi giải mã; log không chứa audio/văn bản/token. Cá nhân hóa (I-7) cần quyết định nơi lưu kết quả — đề xuất: backend.

## D-016 Hai tuyến model riêng: `asr` (phiên âm) và `pronunciation` (chấm phát âm) (2026-11-14)
Theo số đo: SenseVoice tốt hơn cho phiên âm (CER 8.5 % vs 10.0 %, có dấu câu) nhưng với chấm phát âm thì ReazonSpeech ngang về kana CER (5.3 %), cao hơn ở E-002 (90 vs 86/100 câu đúng đạt ≥ 90), nhỏ hơn và Apache-2.0 → tính năng phát âm không vướng câu hỏi giấy phép của D-012. Registry có `routing.pronunciation` (ReazonSpeech → SenseVoice → Parakeet); ghi đè: `JAI_PRONUNCIATION_MODEL`.

## D-017 Tách nền tảng AI ra repo riêng `miraigo-ai-platform` (2026-11-15, user chọn)
Thay cho vị trí trong D-007. Lý do: deploy độc lập, khác ngôn ngữ/CI (Python vs TS), tránh Metro/tsconfig của app quét venv/model, repo app là của nhóm. Repo private. Bản sao trong `miraigo-x-p/japanese-ai-platform/` (nhánh `docs/lab-and-ai-platform`) chưa bị xóa — chờ user quyết.
