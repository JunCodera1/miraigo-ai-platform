# lab/ — knowledge base (AI platform)

Mở phiên mới: đọc `CURRENT_STATE.md` → `TASK_BOARD.md` → chỉ tài liệu task trỏ tới.

| Cần gì | Đọc |
|---|---|
| Kiến trúc, luồng request, điểm mở rộng | `AI_ARCHITECTURE.md` |
| Chọn công nghệ nào cho việc gì | `AI_TECHNOLOGY_ATLAS.md` |
| Model nào, vai trò, giấy phép | `MODEL_REGISTRY.md` (nguồn thật: `src/japanese_ai/model_registry/models.yaml`) |
| Số đo của chính mình | `EXPERIMENT_RESULTS.md` |
| Giá nhà cung cấp | `PROVIDER_COMPARISON.md` |
| Tính năng, lộ trình tích hợp app | `FEATURE_CATALOG.md`, `INTEGRATION_ROADMAP.md` |
| Vì sao chọn X | `DECISIONS.md` |
| Bằng chứng thô | `research/speech-ai/`, `research/pronunciation/` |

App và backend: `../miraigo-x-p` (lab riêng của app), `../miraigo-be`.
Nhãn: [V] đã xác minh, [E] thí nghiệm của mình, [B] benchmark bên thứ ba, [H] chưa kiểm, [P] đề xuất.
Quy tắc: chạy model qua `scripts/run-capped.sh`; venv/model/dữ liệu eval ở `~/.local/share/japanese-ai-platform/`.
