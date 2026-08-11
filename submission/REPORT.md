# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: C5-2
- Repository URL: https://github.com/gianghh0928-ctrl/Day13-K4-2A202601470
- Commit SHA cuối: `4b9f0c1693aadbde39ea69b68203227f751083a1`
- Thành viên và vai trò:
  - Hoàng Hương Giang - 2A202601470 - Nhóm trưởng, vai trò Logging & PII
  - Nguyễn Ngọc Lan - 2A202601384 - Vai trò Tracing & Prompt Version + Dashboard/SLO
  - Nguyễn Hoàng Duy - 2A202601466 - Vai trò Incident, Report & Demo

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** (Baseline: 30/100 → Checkpoint 1: 100/100 → sau challenge: 100/100 trên 32 record, 17 correlation ID — [`validate_logs_challenge.txt`](evidence/validate_logs_challenge.txt))
- Tổng số traces: **14 traces** có metadata và span breakdown đầy đủ trên project `My Project`, liệt kê kèm trace ID và URL trong [`challenge_traces.json`](evidence/challenge_traces.json) — vượt yêu cầu tối thiểu 10. Ngoài ra checkpoint 2 còn 10 traces trên project `VinAI_DAY13`
- Số PII leak còn lại: 0 (giữ 0 qua cả 3 lần chạy, kể cả cửa sổ challenge)
- Link/đường dẫn dashboard: `/dashboard` (nguồn `/dashboard_data` đọc `data/logs.jsonl`) — ảnh runtime có dữ liệu thật: [`dashboard_runtime_with_data.png`](evidence/dashboard_runtime_with_data.png)
- `validate_dashboard.py`: `HỢP LỆ: 6/6 panel` — [`validate_dashboard_result.txt`](evidence/validate_dashboard_result.txt)

## 3. Logging và tracing

- Evidence correlation ID: `submission/evidence/sample_correlation_log.json` (Trace correlation ID xuyên suốt request_received và response_sent)
- Evidence PII redaction: `submission/evidence/sample_pii_redacted_log.json` (Redact Email -> `[REDACTED_EMAIL]`, Phone -> `[REDACTED_PHONE_VN]`, CCCD -> `[REDACTED_CCCD]`, Credit Card -> `[REDACTED_CREDIT_CARD]`)
- Evidence trace waterfall: [`trace_waterfall_incident.png`](evidence/trace_waterfall_incident.png) và [`trace_waterfall_healthy.png`](evidence/trace_waterfall_healthy.png), kèm số liệu span đầy đủ của 14 trace trong [`challenge_traces.json`](evidence/challenge_traces.json). Ảnh [`trace_waterfall.png`](evidence/trace_waterfall.png) từ checkpoint 2 được giữ lại nhưng chụp trước khi nhóm thêm span con, nên chỉ thấy **một span `run` duy nhất** và không thể hiện được việc khoanh vùng span.
- Giải thích một span đáng chú ý: trace có 3 span lồng nhau — `run` (GENERATION, ghi token `input`/`output`, `cost`, `doc_count`, `prompt_version`, `prompt_label`) bọc hai span con `rag_retrieval` và `llm_generate`. Span đáng chú ý nhất là **`rag_retrieval`**: bình thường tốn 0.000–0.003 s, nhưng trong incident challenge nó chiếm **2.503 s trên tổng 2.655 s** trong khi `llm_generate` vẫn giữ 0.151 s. Chính span này khoanh vùng root cause ở mục 6.

## 4. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: Version 1 (Labels: `baseline`, `production`)
- Version/label candidate: Version 2 (Label: `candidate`)
- **Project Langfuse chứa evidence**: `My Project` (`cmsoih1ft00mead0lcege5hq5`). Prompt `day13-chat` v1/v2 được dựng trong project này theo đúng [`docs/PROMPT_VERSIONING.md`](../docs/PROMPT_VERSIONING.md), và toàn bộ trace ID ở mục này cùng mục 6 đều nằm ở đây nên kiểm chứng được bằng một lần đăng nhập.

  Checkpoint 2 ban đầu làm trên project `VinAI_DAY13` (`cmsoepljr00ovad0dt574axxx`) — nguồn của [`prompt_versions.png`](evidence/prompt_versions.png) và [`prompt_rollback.png`](evidence/prompt_rollback.png). Prompt v1/v2 và thao tác rollback ở project đó là thật (đã kiểm lại bằng API: v1 → `[baseline, production]`, v2 → `[latest, candidate]`), nhưng **hai trace ID từng khai để chứng minh hai version thì sai** (xem cuối mục này), nên nhóm dùng evidence dưới đây làm nguồn chính.

- Trace ID của mỗi version — **cùng một input** `"Explain why metrics traces and logs work together."`, chỉ đổi `LANGFUSE_PROMPT_LABEL`:

  | Label chạy  | Trace ID                           | `prompt_name` | `prompt_label` | `prompt_version` | `prompt_source` | input tokens |
  | ----------- | ---------------------------------- | ------------- | -------------- | ---------------- | --------------- | -----------: |
  | `baseline`  | `f97ad438efbabf56a2422920428932b8` | day13-chat    | baseline       | **1**            | langfuse        |           35 |
  | `candidate` | `5f66732ff1606a2ac1e3029313d7527a` | day13-chat    | candidate      | **2**            | langfuse        |       **50** |

  Dữ liệu thô kèm span: [`challenge_traces.json`](evidence/challenge_traces.json) → `prompt_version_comparison_same_input`.
  `prompt_source=langfuse` ở cả hai trace xác nhận prompt được fetch thật từ Langfuse, không phải `local` hay `local-fallback`.

  Cột **input tokens** là bằng chứng độc lập với metadata: v2 có thêm một dòng chỉ dẫn nên prompt dài hơn, và số token vào tăng từ 35 lên 50. Nếu app chỉ ghi nhãn version mà thực tế vẫn compile cùng một prompt thì con số này phải giống nhau.

- **Bằng chứng rollback bằng trace** (mạnh hơn ảnh chụp, vì chứng minh được request thật đã dùng version nào). Thực hiện đúng bước 5–6 của PROMPT_VERSIONING: chuyển label `production` sang v2, chạy một request, rồi rollback `production` về v1 và chạy lại:

  | Bước                       | Trace ID                           | `prompt_label` | `prompt_version` | input tokens |
  | -------------------------- | ---------------------------------- | -------------- | ---------------- | -----------: |
  | chuyển `production` → v2   | `430903d189f89b4c74da196c53d5c9af` | production     | **2**            |           50 |
  | rollback `production` → v1 | `7cb262726137b6867f9f1f699d21e683` | production     | **1**            |           35 |

  Trạng thái label cuối, kiểm lại bằng API sau khi rollback: v1 → `[production, baseline]`, v2 → `[candidate, latest]` ⇒ `production` **đã được trả về v1**.
  Kèm ảnh danh sách version: [`prompt_versions_list.png`](evidence/prompt_versions_list.png), và hai ảnh UI từ checkpoint 2: [`prompt_rollback.png`](evidence/prompt_rollback.png), [`prompt_versions.png`](evidence/prompt_versions.png).

- **Đính chính**: bản báo cáo trước khai `3ace16da125ad614144b9a19c448c616` là "Baseline Trace" và `a40f27a5a1afde5819a22dce31b34d3a` là "Candidate Trace". Truy vấn lại bằng Langfuse API cho thấy **cả hai đều có `prompt_label=production`, `prompt_version=1`** — chúng không chứng minh được hai version khác nhau, nên yêu cầu Checkpoint 2 về prompt versioning thực tế chưa đạt. Thành viên phụ trách checkpoint 2 đã xác nhận sai sót này. Hai trace cũ vẫn tồn tại thật trên `VinAI_DAY13`, chỉ là bị gắn sai nhãn khi ghi vào báo cáo; các trace ở hai bảng trên được tạo lại đúng quy trình PROMPT_VERSIONING để thay thế.

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: `HỢP LỆ: 6/6 panel có trong dashboard contract.` — [`validate_dashboard_result.txt`](evidence/validate_dashboard_result.txt)
- Evidence dashboard: [`dashboard_runtime_with_data.png`](evidence/dashboard_runtime_with_data.png) — 6 panel, nhìn rõ tên panel, đơn vị, time range 60 phút, refresh 30s và threshold/SLO line trên từng panel.
  - Ảnh chụp trên một cửa sổ chạy lại sạch gồm **10 request baseline (healthy) + 5 request challenge (`rag_slow` bật)**, để panel phản ánh đúng một cửa sổ vận hành thay vì trộn nhiều phase thí nghiệm.
  - Panel 1 chính là bằng chứng trực quan cho sự cố ở mục 6: **cột P50 gần như sát đáy (152 ms) trong khi P95 và P99 vọt lên 2655 ms**. Đây là lý do threshold được đặt trên percentile chứ không trên average.
  - Các panel còn lại xác nhận phần differential diagnosis: traffic 15 request, error rate "No Errors", cost 0.0295 USD (xa threshold 2.5), token in/out 505/1867 (thấp so với threshold 50k), quality 0.8667 nằm trên SLO line 0.75.
- **Lưu ý về ảnh cũ** [`dashboard_runtime.png`](evidence/dashboard_runtime.png): ảnh này chụp khi endpoint `/dashboard_data` còn bug thiếu `import json` (mục 7, dòng #2), nên **cả 6 panel đều hiển thị 0** — chỉ thấy threshold line, không có dữ liệu. Nhóm giữ lại ảnh cũ để không xóa dấu vết và bổ sung ảnh mới sau khi fix, thay vì ghi đè.
- SLO đã chọn và lý do:
  - Latency P95 <= 3000ms: Bảo đảm thời gian phản hồi cho trải nghiệm người dùng không bị chậm rùa.
  - Error Rate <= 2.0%: Duy trì tỷ lệ lỗi ở mức thấp chấp nhận được cho dịch vụ AI.
  - Total Cost <= $2.5: Kiểm soát ngân sách gọi model LLM trong hạn mức cho phép.
  - Quality Score Mean >= 0.75: Đảm bảo độ chính xác và chất lượng của câu trả lời từ RAG + LLM.
- Alert rules và runbook: định nghĩa máy đọc được ở [`config/alert_rules.yaml`](../config/alert_rules.yaml), runbook đầy đủ (impact, 3 bước kiểm tra đầu tiên, mitigation, owner) ở [`docs/alerts.md`](../docs/alerts.md).
  1. **`high_latency_p95`** (Critical, `p95_latency_ms > 3000 for 5m`) → [runbook](../docs/alerts.md#alert-1). Kiểm tra: panel `latency` vs panel `traffic` (latency tăng mà traffic không tăng ⇒ nghi một span chậm) → so thời lượng span retrieval vs generation trên trace → lọc log theo `correlation_id` đối chiếu `latency_ms` với baseline. Mitigation: cache + timeout cứng cho retrieval. Owner: oncall-eng.
  2. **`high_error_rate`** (Critical, `error_rate_pct > 2.0 for 3m`) → [runbook](../docs/alerts.md#alert-2). Cửa sổ ngắn hơn Alert 1 vì lỗi ảnh hưởng người dùng ngay. Kiểm tra: `count_by_value(error_type)` → `payload.detail` theo `correlation_id` → trạng thái dependency và lần deploy/đổi label gần nhất. Mitigation: circuit breaker + fallback answer. Owner: oncall-eng.
  3. **`low_quality_score`** (Warning, `quality_score_avg < 0.75 for 5m`) → [runbook](../docs/alerts.md#alert-3). Đây là lỗi "im lặng": service vẫn 200 và vẫn nhanh nên latency/error rate không phát hiện được. Kiểm tra: thời điểm mean tụt vs thời điểm đổi label `production` → metadata `prompt_label`/`prompt_version`/`prompt_source` trên trace (loại trừ `local-fallback`) → `doc_count` của span retrieval. Mitigation: rollback label `production` về v1. Owner: oncall-eng.
  - Cost **không** đặt alert paging riêng: vượt ngân sách không gây gián đoạn người dùng, nên panel `cost` (threshold tổng 2.5 USD) dùng để review theo ngày.
  - Sau khi điều tra challenge, nhóm xác định thêm một **khoảng mù**: sự cố đạt p95 2652 ms — vượt ngưỡng vận hành 2000 ms nhưng vẫn dưới SLO 3000 ms nên `high_latency_p95` không bắn. Xem đề xuất bổ sung alert cảnh báo sớm ở mục 6.

## 6. Điều tra challenge

Bản điều tra đầy đủ theo luồng Metrics → Traces → Logs: [`submission/evidence/challenge_investigation.md`](evidence/challenge_investigation.md).
Số liệu thô: [`challenge_metrics_before_after.json`](evidence/challenge_metrics_before_after.json) và [`challenge_incident_logs.json`](evidence/challenge_incident_logs.json).

- **Challenge ID**: `day13-k4-observability-v1` (cohort K4, incident release `rag_slow`, `affected_feature=monitoring`, `latency_threshold_ms=2000`, `seed=1304`). Chạy bằng `python scripts/inject_incident.py` + `python scripts/load_test.py --challenge --concurrency 5`; `config/challenge.json` không bị sửa.

- **Triệu chứng từ metrics**: latency tail tăng vọt trong khi mọi tín hiệu khác giữ nguyên.
  - P95/P99: 151 ms → **2652 ms**, vượt ngưỡng challenge 2000 ms.
  - **P50 gần như không đổi: 150 ms → 151 ms.** Nếu chỉ theo dõi average/P50 thì sự cố vô hình, vì 5 request chậm bị 10 request nhanh pha loãng — đúng lý do `config/dashboard.yaml` đặt threshold trên `p95`.
  - `error_rate_pct` giữ 0.0% → loại trừ `tool_fail`. Cost và token chỉ tăng tuyến tính theo số request → loại trừ `cost_spike`. `quality_avg` 0.88 → 0.8667, không tụt.
  - Ngay ở lớp metrics đã khoanh được: thời gian phát sinh nằm ở **một bước không sinh token**.

- **Trace ID liên quan** — challenge được chạy lại với `tracing_enabled=true` để lấy trace thật. Sau khi bổ sung span `rag_retrieval` và `llm_generate` (mục 7, dòng #7), waterfall **tách được trực tiếp** hai bước, không còn phải suy luận. Dữ liệu thô: [`challenge_traces.json`](evidence/challenge_traces.json).

  **Trong incident (`rag_slow=ON`)** — 5 input chính thức:

  | Trace ID                           | session          | `rag_retrieval` | `llm_generate` |    tổng |
  | ---------------------------------- | ---------------- | --------------: | -------------: | ------: |
  | `ee45bf95b517175f8ff9bedbe2801bc4` | k4-challenge-s01 |     **2.503 s** |        0.151 s | 2.655 s |
  | `8303de0e3d718b285cf1c632239f3102` | k4-challenge-s02 |     **2.502 s** |        0.152 s | 2.654 s |
  | `87bf243eb9cce5dcd5dc39c25cec3312` | k4-challenge-s03 |     **2.506 s** |        0.152 s | 2.658 s |
  | `21080451f271ccd8556c88b1a3b33570` | k4-challenge-s04 |     **2.503 s** |        0.152 s | 2.655 s |
  | `a4612d433c7646ce018db3904818cace` | k4-challenge-s05 |     **2.502 s** |        0.152 s | 2.654 s |

  **Cùng 5 input khi `rag_slow=OFF`**:

  | Trace ID                           | session          | `rag_retrieval` | `llm_generate` |      tổng |
  | ---------------------------------- | ---------------- | --------------: | -------------: | --------: |
  | `ae3b3d315e4a347e76141c3a24954c58` | k4-challenge-s01 |     **0.001 s** |        0.151 s |   0.153 s |
  | `f7d1115186a00f3d06b80a11d0e4538e` | k4-challenge-s02 |     **0.000 s** |        0.153 s | 1.224 s\* |
  | `ad30dbbafd26af705cb350fd70fdf3f2` | k4-challenge-s03 |     **0.000 s** |        0.151 s |   0.153 s |
  | `f346d0312f224b213b5181324aeef8f9` | k4-challenge-s04 |     **0.000 s** |        0.151 s |   0.156 s |
  | `22321400423c922940ea1f9c9d62db43` | k4-challenge-s05 |     **0.003 s** |        0.151 s |   0.154 s |

  **Kết luận từ trace**: `llm_generate` gần như bất biến qua cả 10 trace (0.151–0.153 s), trong khi `rag_retrieval` đi từ 0.000–0.003 s → 2.502–2.506 s. Toàn bộ phần latency phát sinh nằm trong span `rag_retrieval`.

  Ảnh waterfall của hai trace đối chứng: [`trace_waterfall_incident.png`](evidence/trace_waterfall_incident.png) (`ee45bf95...`, `rag_retrieval` chiếm 2.503 s) và [`trace_waterfall_healthy.png`](evidence/trace_waterfall_healthy.png) (`ad30dbba...`, `rag_retrieval` 0.000 s). Khi demo, mở trực tiếp URL trace trong [`challenge_traces.json`](evidence/challenge_traces.json) thay vì chỉ chiếu ảnh.

  \* Trace `f7d11151...` có tổng 1.224 s dù cả hai span chỉ tốn 0.153 s: waterfall cho thấy khoảng trống ~1.07 s giữa lúc `rag_retrieval` kết thúc và `llm_generate` bắt đầu. Đó là lần fetch prompt đầu tiên từ Langfuse khi cache còn lạnh (`cache_ttl_seconds=60`), không phải một bước xử lý. Đây cũng là ví dụ cho thấy đọc waterfall phải để ý cả **khoảng trống giữa các span**, không chỉ độ dài từng span.

  Bằng chứng đo bằng log ở lớp dưới vẫn giữ nguyên và độc lập với trace: delta latency là hằng số 2500 ms **không phụ thuộc `tokens_out`** (`tokens_out` chạy 82 → 160 nhưng `latency_ms` bám 2651–2652 ms, biên độ 1 ms). Nếu độ chậm nằm ở generation thì latency phải biến thiên theo số token — nó không biến thiên.

- **Log line/correlation ID liên quan** (`data/logs.jsonl`, event `response_sent`):
  - Trong incident: `req-f5117691` (s02, 2651 ms), `req-1a418320` (s04, 2651 ms), `req-367f21d9` (s03, 2652 ms), `req-4c3cc2c4` (s01, 2651 ms), `req-1cc3af3e` (s05, 2652 ms).
  - Cùng 5 input sau khi tắt cờ sự cố: `req-07ae748c` (150 ms), `req-f0a2b33d` (150 ms), `req-7d86a5b6` (150 ms), `req-1d22ff7f` (151 ms), `req-ee488106` (150 ms).
  - Log control-plane xác nhận đúng incident chính thức được bật: `{"service":"control","event":"incident_enabled","payload":{"name":"rag_slow"}}`.
  - Đây là **controlled experiment**: cùng 5 message, cùng feature, cùng concurrency, cùng tiến trình API, chỉ đổi một biến là cờ `rag_slow` → 2651 ms ↔ 150 ms, sai khác đúng 2500 ms trên 10 phép đo.

- **Root cause**: bước **retrieval của RAG pipeline**. Tại [`app/mock_rag.py:18`](../app/mock_rag.py#L18), khi cờ sự cố bật, `retrieve()` chèn `time.sleep(2.5)` trước khi tra CORPUS. 2500 ms này cộng thẳng vào `agent.run` trước khi LLM được gọi, khớp chính xác delta đo ở lớp log và giải thích trọn vẹn tại sao token/cost/quality/error đều không đổi. Trong hệ thống thật đây là hình mẫu vector store phản hồi chậm (index quá lớn, connection pool cạn, mạng tới vector DB xuống cấp), **không phải model chậm**.

- **Phát hiện phụ — chặn event loop khuếch đại tail latency**: client đo 13300 ms/request trong khi server log 2651 ms. Timestamp `response_sent` cách nhau đều 2.66 s trong incident và ~0.156 s sau khi fix, dù `--concurrency 5` gửi đồng thời → 5 request bị xử lý **nối tiếp**. Nguyên nhân: `/chat` khai báo `async def` nhưng gọi `agent.run()` là code đồng bộ có `time.sleep()`, chặn event loop uvicorn. Hệ quả là head-of-line blocking, latency người dùng thật ≈ N × latency server ghi nhận. Cho thấy chỉ tin `latency_ms` do server tự đo là không đủ.

- **Fix action**:
  1. Timeout cứng cho retrieval (~500 ms) + fallback trả lời không có context kèm cảnh báo, cắt sớm vector store chậm.
  2. Cache kết quả retrieval theo hash query — 5 input challenge cùng feature `monitoring` và trả về cùng một document.
  3. Chạy `agent.run()` trong threadpool (`await run_in_threadpool(...)`) hoặc chuyển retrieval/LLM sang client async, để một request chậm không chặn event loop.
  4. Ghi `x-response-time-ms` (latency đo ở middleware) vào `response_sent` để dashboard thấy latency người dùng thật.
  - Đã xác minh hành động khôi phục ngay: tắt cờ sự cố đưa latency về 150–151 ms trên đúng 5 input chính thức.

- **Preventive measure**:
  1. **Bổ sung alert cảnh báo sớm ở `p95 > 2000 ms`** (đúng `latency_threshold_ms` của challenge). Sự cố này đạt 2652 ms — vượt ngưỡng vận hành nhưng vẫn dưới SLO 3000 ms, nên `high_latency_p95` hiện tại **sẽ không bắn**; đây là khoảng mù thật cần bịt.
  2. Thêm span/metric latency riêng cho từng bước (retrieval, generation) thay vì chỉ đo tổng `agent.run` — lần này việc khoanh vùng phải suy luận gián tiếp.
  3. SLO riêng cho dependency retrieval và alert khi p95 retrieval vượt ngưỡng.
  4. Load test hồi quy trong CI với ngưỡng p95 trên tập input cố định, chặn deploy nếu p95 xấu đi.
  5. Luôn alert trên percentile chứ không trên average, và hiển thị P50 cạnh P95/P99.

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên        | Phần việc                                                                                                                                                                                                                                             | Commit/PR                       | Điều đã học                                                                                                                                |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Hoàng Hương Giang | Nhóm trưởng. Checkpoint 0 + 1: correlation ID middleware, log enrichment metadata, PII redaction, evidence baseline                                                                                                                                   | `f8b95f3`, `e1d841d`, `d194906` | Log có cấu trúc, thứ tự processor phải scrub PII **trước** khi render JSON                                                                 |
| Nguyễn Ngọc Lan   | Checkpoint 2: Langfuse tracing + prompt v1/v2 (label/rollback) trên `VinAI_DAY13`, dashboard 6 panel `/dashboard`, SLO & alert rules. Hai trace ID prompt version khai trong báo cáo bị gắn sai nhãn, đã xác nhận và được thay bằng trace mới ở mục 4 | `7135c02`                       | Tích hợp Langfuse tracing, prompt versioning và dashboard contract/validator; trace ID phải kiểm lại bằng API trước khi đưa vào báo cáo    |
| Nguyễn Hoàng Duy  | Checkpoint 3 + hoàn tất: chạy challenge chính thức, điều tra Metrics→Traces→Logs, viết runbook `docs/alerts.md`, fix bug `/dashboard_data`, hoàn thiện REPORT mục 6                                                                                   | `4b9f0c1` (chi tiết bảng dưới)  | Percentile vs average: sự cố này giữ P50 ở 151 ms nên chỉ P95/P99 mới lộ ra; và phân biệt latency server tự đo với latency người dùng thật |

### Chi tiết phần việc của Nguyễn Hoàng Duy (vai trò Incident, Report & Demo)

| #   | Thay đổi                                                                                                                          | File                                                                                                                                                                                                                                         | Vì sao                                                                                                                                                                                                                                                                                                                                                                                                              |
| --- | --------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Chạy challenge chính thức và điều tra đủ 3 lớp                                                                                    | [`evidence/challenge_investigation.md`](evidence/challenge_investigation.md), [`challenge_metrics_before_after.json`](evidence/challenge_metrics_before_after.json), [`challenge_incident_logs.json`](evidence/challenge_incident_logs.json) | Checkpoint 3. Thiết kế thêm bước chạy lại **đúng 5 input chính thức sau khi tắt cờ sự cố**, biến việc điều tra thành controlled experiment 1 biến thay vì chỉ mô tả triệu chứng                                                                                                                                                                                                                                     |
| 2   | **Fix bug**: `/dashboard_data` dùng `json.loads` nhưng `app/main.py` không `import json`                                          | [`app/main.py`](../app/main.py)                                                                                                                                                                                                              | Mọi dòng log đều raise `NameError` và bị `except Exception: pass` nuốt, nên `logs` luôn rỗng và cả 6 panel luôn hiển thị 0. Sau fix, `/dashboard_data` trả số khớp `/metrics` (đã xác minh: `p95=151` baseline → `p95=2652` trong incident)                                                                                                                                                                         |
| 3   | Viết runbook cho 3 alert                                                                                                          | [`docs/alerts.md`](../docs/alerts.md)                                                                                                                                                                                                        | File này còn là template rỗng dù `config/alert_rules.yaml` đã trỏ runbook vào các anchor `#alert-1..3` — link đang dẫn tới chỗ trống. Rubric A1 yêu cầu runbook hợp lý                                                                                                                                                                                                                                              |
| 4   | Phát hiện phụ: chặn event loop khuếch đại tail latency                                                                            | mục 6 báo cáo                                                                                                                                                                                                                                | Client đo 13300 ms trong khi server log 2651 ms; timestamp cách đều nhau chứng minh 5 request bị xử lý nối tiếp dù `--concurrency 5`                                                                                                                                                                                                                                                                                |
| 5   | Sửa Repository URL trong báo cáo                                                                                                  | mục 1                                                                                                                                                                                                                                        | URL đang ghi `K4-Day13-...` nhưng `git remote` là `Day13-K4-...`; theo SUBMISSION.md, sai loại URL bị coi là bài nộp chưa hợp lệ                                                                                                                                                                                                                                                                                    |
| 6   | Chụp lại dashboard runtime                                                                                                        | [`dashboard_runtime_with_data.png`](evidence/dashboard_runtime_with_data.png)                                                                                                                                                                | Ảnh cũ chụp khi còn bug ở dòng #2 nên cả 6 panel đều bằng 0. Giữ lại ảnh cũ, không ghi đè                                                                                                                                                                                                                                                                                                                           |
| 7   | **Thêm span `rag_retrieval` và `llm_generate`**                                                                                   | [`app/mock_rag.py`](../app/mock_rag.py), [`app/mock_llm.py`](../app/mock_llm.py)                                                                                                                                                             | Trước đó cả request chỉ có **một span** (`LabAgent.run`), nên waterfall không tách được retrieval khỏi generation và việc khoanh vùng phải suy luận gián tiếp. Đây chính là preventive measure #2 mà nhóm đề xuất, nên nhóm implement luôn. `capture_input=False` trên cả hai span vì `message` là input thô có thể chứa PII — giữ đúng policy `LabAgent.run` đang dùng, không gửi dữ liệu chưa scrub sang Langfuse |
| 8   | Phát hiện hai trace ID prompt version ở mục 4 gắn sai nhãn, tạo lại trace đúng                                                    | mục 4                                                                                                                                                                                                                                        | Cả hai trace cũ đều là `prompt_label=production, prompt_version=1`, không chứng minh được hai version. Đây là yêu cầu Checkpoint 2 (rubric A1) chưa đạt                                                                                                                                                                                                                                                             |
| 9   | Dựng lại prompt `day13-chat` v1/v2 trong project truy cập được, tái lập challenge và bổ sung **demo rollback có trace hai chiều** | mục 4, [`challenge_traces.json`](evidence/challenge_traces.json)                                                                                                                                                                             | Project mới trống nên `resolve_prompt` sẽ rơi vào `local-fallback` và làm mất toàn bộ bằng chứng prompt version. Rollback giờ chứng minh bằng trace (`production`→v2 rồi về v1) chứ không chỉ bằng ảnh                                                                                                                                                                                                              |
| 10  | **Fix bug**: `usage_details` gửi sai key nên trace mất phân bổ token vào/ra                                                       | [`app/agent.py`](../app/agent.py)                                                                                                                                                                                                            | Code gửi `prompt_tokens`/`completion_tokens`, nhưng Langfuse chỉ nhận `input`/`output`; các key khác bị coi là custom. Kết quả: mọi generation hiển thị **`0 prompt → 0 completion`** dù total và cost vẫn đúng, và mọi phân tích cost theo input vs output ở phía Langfuse đều sai. Đã đổi sang `input`/`output`; xác minh lại qua API: `usage input=35 output=148 total=183`                                      |
| 11  | Hoàn thiện mục 1, 2, 3, 4, 5, 6 và bảng đóng góp                                                                                  | `submission/REPORT.md`                                                                                                                                                                                                                       | Nộp bài                                                                                                                                                                                                                                                                                                                                                                                                             |

**Câu hỏi tự kiểm tra đã trả lời được** (theo [`docs/mock-debug-qa.md`](../docs/mock-debug-qa.md)):

- _Vì sao chỉ nhìn average latency có thể bỏ sót vấn đề?_ Chính sự cố này là ví dụ: 5 request 2651 ms lẫn với 10 request 150 ms cho average ~984 ms, dưới cả ngưỡng 2000 ms. P50 thậm chí chỉ nhích từ 150 lên 151 ms. Chỉ P95/P99 lộ ra 2652 ms.
- _Correlation ID khác trace ID như thế nào?_ Correlation ID (`req-f5117691`) do middleware của nhóm sinh ra cho mỗi HTTP request và trả lại qua header `x-request-id`, dùng để nối các dòng log với nhau. Trace ID do Langfuse sinh, gom các span bên trong một lần chạy agent. Correlation ID nối **log ↔ log**, trace ID nối **span ↔ span**; muốn nối được hai lớp thì phải bind correlation ID vào metadata của trace.
- _Evidence nào đủ để kết luận một span là root cause?_ Không phải chỉ "span đó lâu nhất". Cần: (a) delta thời gian của span khớp với delta latency tổng — ở đây 2500 ms khớp chính xác; (b) loại trừ được các nguyên nhân khác bằng tín hiệu độc lập — token/cost/quality/error đều không đổi; (c) tái lập được bằng cách bật/tắt đúng một biến — 2651 ms ↔ 150 ms.
- _Khi cost tăng nhưng traffic không tăng, kiểm tra trường nào?_ `tokens_out` per request trước tiên (dấu hiệu `cost_spike`: output token nhân lên mà input không đổi), rồi `tokens_in` (prompt phình do docs retrieval), rồi `model` (có request nào rơi sang model đắt hơn).
