# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL:
- Commit SHA cuối:
- Thành viên và vai trò:

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: 100/100 (Baseline: 30/100, Checkpoint 1: 100/100)
- Tổng số traces: (Sẽ hoàn thiện ở Checkpoint 2)
- Số PII leak còn lại: 0
- Link/đường dẫn dashboard: `data/logs.jsonl`

## 3. Logging và tracing

- Evidence correlation ID: `submission/evidence/sample_correlation_log.json` (Trace correlation ID xuyên suốt request_received và response_sent)
- Evidence PII redaction: `submission/evidence/sample_pii_redacted_log.json` (Redact Email -> `[REDACTED_EMAIL]`, Phone -> `[REDACTED_PHONE_VN]`, CCCD -> `[REDACTED_CCCD]`, Credit Card -> `[REDACTED_CREDIT_CARD]`)
- Evidence trace waterfall: (Sẽ hoàn thiện ở Checkpoint 2)
- Giải thích một span đáng chú ý: (Sẽ hoàn thiện ở Checkpoint 2)

## 4. Prompt versioning

- Prompt name:
- Version/label baseline:
- Version/label candidate:
- Trace ID của mỗi version:
- Bằng chứng đổi label hoặc rollback:

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`:
- Evidence dashboard:
- SLO đã chọn và lý do:
- Alert rules và runbook:

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
| | | | |
