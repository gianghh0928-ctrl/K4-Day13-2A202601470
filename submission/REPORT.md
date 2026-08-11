# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: C5-2
- Repository URL: https://github.com/gianghh0928-ctrl/K4-Day13-2A202601470
- Commit SHA cuối: e1d841db499e1b58976c3940ea037f5d1ac3107e
- Thành viên và vai trò:
   * Hoàng Hương Giang - 2A202601470 Nhóm trưởng
   * Nguyễn Ngọc Lan - 2A202601384 - Thành viên
   * Nguyễn Hoàng Duy - 2A2026 - Thành viên

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: 100/100 (Baseline: 30/100, Checkpoint 1: 100/100)
- Tổng số traces: Tối thiểu 10 traces (Đã ghi nhận trên Langfuse)
- Số PII leak còn lại: 0
- Link/đường dẫn dashboard: `data/logs.jsonl` / `submission/evidence/dashboard_runtime.png`

## 3. Logging và tracing

- Evidence correlation ID: `submission/evidence/sample_correlation_log.json` (Trace correlation ID xuyên suốt request_received và response_sent)
- Evidence PII redaction: `submission/evidence/sample_pii_redacted_log.json` (Redact Email -> `[REDACTED_EMAIL]`, Phone -> `[REDACTED_PHONE_VN]`, CCCD -> `[REDACTED_CCCD]`, Credit Card -> `[REDACTED_CREDIT_CARD]`)
- Evidence trace waterfall: `submission/evidence/trace_waterfall.png`
- Giải thích một span đáng chú ý: Span `generation` (đo lường `FakeLLM.generate`) ghi nhận latency, `prompt_tokens`, `completion_tokens` và metadata chi tiết như `doc_count`, `prompt_version`, `prompt_label`.

## 4. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: Version 1 (Labels: `baseline`, `production`)
- Version/label candidate: Version 2 (Label: `candidate`)
- Trace ID của mỗi version:
  * Baseline Trace ID: `3ace16da125ad614144b9a19c448c616`
  * Candidate Trace ID: `a40f27a5a1afde5819a22dce31b34d3a`
- Bằng chứng đổi label hoặc rollback: `submission/evidence/prompt_rollback.png` (ảnh thao tác đổi/rollback label) & `submission/evidence/prompt_versions.png` (ảnh danh sách 2 version).

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: HỢP LỆ: 6/6 panel có trong dashboard contract.
- Evidence dashboard: `submission/evidence/dashboard_runtime.png`
- SLO đã chọn và lý do:
  * Latency P95 <= 3000ms: Bảo đảm thời gian phản hồi cho trải nghiệm người dùng không bị chậm rùa.
  * Error Rate <= 2.0%: Duy trì tỷ lệ lỗi ở mức thấp chấp nhận được cho dịch vụ AI.
  * Total Cost <= $2.5: Kiểm soát ngân sách gọi model LLM trong hạn mức cho phép.
  * Quality Score Mean >= 0.75: Đảm bảo độ chính xác và chất lượng của câu trả lời từ RAG + LLM.
- Alert rules và runbook:
  1. **Alert High Latency P95** (Critical, `p95_latency_ms > 3000 for 5m`): Check span RAG retrieval, check LLM latency, check server CPU/Memory. Mitigation: Bật cache RAG hoặc scale backend. Owner: oncall-eng.
  2. **Alert High Error Rate** (Critical, `error_rate_pct > 2.0 for 3m`): Check `request_failed` log với correlation ID, check LLM upstream status. Mitigation: Bật circuit breaker hoặc fallback response. Owner: oncall-eng.
  3. **Alert Low Quality Score** (Warning, `quality_score_avg < 0.75 for 5m`): Check version prompt vừa deploy, check chất lượng RAG docs. Mitigation: Rollback prompt `production` về version v1 cũ. Owner: oncall-eng.

## 6. Điều tra challenge

- Challenge ID:
- Triệu chứng từ metrics:
- Trace ID liên quan:
- Log line/correlation ID liên quan:
- Root cause:
- Fix action:
- Preventive measure:

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Hoàng Hương Giang | Nhóm trưởng, Checkpoint 1 (Logging & PII) | `e1d841d` | Quản lý log có cấu trúc & Scrub PII |
| Nguyễn Ngọc Lan | Checkpoint 2 (Metrics, Traces, Dashboard & Prompt Versioning) | Main branch | Tích hợp Langfuse Tracing, Prompt versioning & Dashboard validation |
| Nguyễn Hoàng Duy | Thành viên | | |

