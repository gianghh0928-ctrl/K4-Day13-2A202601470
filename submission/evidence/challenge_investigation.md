# Điều tra challenge chính thức — `day13-k4-observability-v1`

Cohort K4. Incident do Lab Coach release trong [`config/challenge.json`](../../config/challenge.json):
`rag_slow`, `affected_feature=monitoring`, `latency_threshold_ms=2000`, `seed=1304`.

`config/challenge.json` không bị sửa. Thứ tự 5 input được `app.challenge.ordered_queries()` shuffle
theo `seed=1304`, nên thứ tự chạy tái lập được: s02 → s04 → s03 → s01 → s05.

Số liệu thô kèm theo:

- [`challenge_metrics_before_after.json`](challenge_metrics_before_after.json) — 3 snapshot metric.
- [`challenge_incident_logs.json`](challenge_incident_logs.json) — log line thật của cả hai cửa sổ.

## 0. Lệnh đã chạy

```bash
# baseline lành mạnh
python scripts/load_test.py

# incident chính thức (đọc incident từ config/challenge.json, không truyền --scenario)
python scripts/inject_incident.py
python scripts/load_test.py --challenge --concurrency 5

# xác minh fix: tắt incident rồi chạy lại đúng 5 input chính thức
python scripts/inject_incident.py --disable
python scripts/load_test.py --challenge --concurrency 5
```

`inject_incident.py` không có `--scenario` nên `resolve_incident(None)` đọc `config/challenge.json`.
Log control-plane xác nhận đúng incident được bật:

```json
{"service":"control","event":"incident_enabled","payload":{"name":"rag_slow"},"level":"warning"}
```

## 1. Metrics — phát hiện triệu chứng

`GET /dashboard_data` (nguồn `data/logs.jsonl`, đúng contract 6 panel):

| Panel | Baseline lành mạnh | Trong incident | Kết luận |
|---|---:|---:|---|
| latency P50 | 150 ms | 151 ms | **không đổi** |
| latency P95 | 151 ms | **2652 ms** | **vượt ngưỡng challenge 2000 ms** |
| latency P99 | 151 ms | **2652 ms** | vượt ngưỡng |
| traffic | 10 req | 15 req | tăng đúng 5 request challenge |
| error_rate_pct | 0.0 % | 0.0 % | không đổi |
| total_cost_usd | 0.0192 | 0.0285 | +0.0093, tuyến tính theo traffic |
| tokens_out | 1211 | 1802 | +591, tuyến tính theo traffic |
| quality_avg | 0.88 | 0.8667 | không đổi đáng kể |

Triệu chứng chốt lại: **latency tail tăng trong khi mọi tín hiệu khác giữ nguyên.**

Hai điểm quan trọng khi đọc panel:

1. **P50 không hề nhúc nhích (150 → 151 ms).** Nếu chỉ theo dõi average hoặc P50 thì sự cố này
   hoàn toàn vô hình, vì 5 request chậm bị 10 request nhanh pha loãng. Đây chính là lý do
   `config/dashboard.yaml` đặt threshold trên `p95` chứ không trên mean.
2. **Đây không phải sự cố về lỗi, chi phí hay chất lượng.** `error_rate_pct` giữ 0.0% (loại trừ
   `tool_fail`), cost và token chỉ tăng tuyến tính theo số request chứ không tăng theo request
   (loại trừ `cost_spike`), `quality_avg` không tụt. Nên ngay từ lớp metrics đã khoanh được:
   thời gian phát sinh nằm ở **một bước không sinh token**.

## 2. Traces — khoanh vùng span bất thường

Ban đầu mỗi request chỉ tạo **một span duy nhất** (`LabAgent.run`, `@observe(as_type="generation")`
trong [`app/agent.py`](../../app/agent.py)), nên waterfall không tách được `retrieve(message)` khỏi
`self.llm.generate(prompt.text)`. Nhóm đã bổ sung hai span con — `rag_retrieval` trong
[`app/mock_rag.py`](../../app/mock_rag.py) và `llm_generate` trong
[`app/mock_llm.py`](../../app/mock_llm.py) — rồi chạy lại challenge với `tracing_enabled=true`.
Cả hai span đặt `capture_input=False` vì `message` là input thô có thể chứa PII.

Số liệu span lấy từ Langfuse API, lưu ở [`challenge_traces.json`](challenge_traces.json).

**Trong incident (`rag_slow=ON`), 5 input chính thức:**

| Trace ID | session | `rag_retrieval` | `llm_generate` | tổng |
|---|---|---:|---:|---:|
| `ee45bf95b517175f8ff9bedbe2801bc4` | k4-challenge-s01 | **2.503 s** | 0.151 s | 2.655 s |
| `8303de0e3d718b285cf1c632239f3102` | k4-challenge-s02 | **2.502 s** | 0.152 s | 2.654 s |
| `87bf243eb9cce5dcd5dc39c25cec3312` | k4-challenge-s03 | **2.506 s** | 0.152 s | 2.658 s |
| `21080451f271ccd8556c88b1a3b33570` | k4-challenge-s04 | **2.503 s** | 0.152 s | 2.655 s |
| `a4612d433c7646ce018db3904818cace` | k4-challenge-s05 | **2.502 s** | 0.152 s | 2.654 s |

**Cùng 5 input khi `rag_slow=OFF`:**

| Trace ID | session | `rag_retrieval` | `llm_generate` | tổng |
|---|---|---:|---:|---:|
| `ae3b3d315e4a347e76141c3a24954c58` | k4-challenge-s01 | **0.001 s** | 0.151 s | 0.153 s |
| `f7d1115186a00f3d06b80a11d0e4538e` | k4-challenge-s02 | **0.000 s** | 0.153 s | 1.224 s * |
| `ad30dbbafd26af705cb350fd70fdf3f2` | k4-challenge-s03 | **0.000 s** | 0.151 s | 0.153 s |
| `f346d0312f224b213b5181324aeef8f9` | k4-challenge-s04 | **0.000 s** | 0.151 s | 0.156 s |
| `22321400423c922940ea1f9c9d62db43` | k4-challenge-s05 | **0.003 s** | 0.151 s | 0.154 s |

`llm_generate` gần như bất biến qua cả 10 trace (0.151–0.153 s) trong khi `rag_retrieval` đi từ
0.000–0.003 s lên 2.502–2.506 s. Toàn bộ latency phát sinh nằm trong span `rag_retrieval`.

\* Trace `f7d11151...` có tổng 1.224 s dù hai span chỉ tốn 0.153 s: waterfall cho thấy **khoảng trống
~1.07 s** giữa lúc `rag_retrieval` kết thúc và `llm_generate` bắt đầu — đó là lần fetch prompt đầu tiên
từ Langfuse khi cache còn lạnh (`cache_ttl_seconds=60`), không phải một bước xử lý. Bài học khi đọc
waterfall: phải để ý cả khoảng trống giữa các span, không chỉ độ dài từng span.

Các trace này nằm trong project Langfuse `My Project` (`cmsoih1ft00mead0lcege5hq5`). Mỗi trace có
trường `url` trong [`challenge_traces.json`](challenge_traces.json) để mở trực tiếp.

Hai dữ kiện gián tiếp ban đầu vẫn đúng và độc lập với trace, dùng để kiểm tra chéo:

- **Delta latency là hằng số 2500 ms, không phụ thuộc độ dài output.** `tokens_out` chạy từ 82 đến
  160 nhưng `latency_ms` bám chặt 2651–2652 ms (biên độ 1 ms). Nếu độ chậm nằm ở LLM generation thì
  latency phải biến thiên theo `tokens_out`.
- **Metadata `doc_count` không đổi.** Retrieval vẫn *trả về đúng kết quả* — chỉ trả về chậm. Đây là
  điểm phân biệt `rag_slow` với `tool_fail`: `tool_fail` sẽ raise
  `RuntimeError("Vector store timeout")` và tạo `request_failed`, còn ở đây cả 5 request đều HTTP 200.

## 3. Logs — chứng minh root cause

Log line thật trong cửa sổ incident (`data/logs.jsonl`, đã lưu ở `challenge_incident_logs.json`):

| correlation_id | session_id | latency_ms | tokens_out | cost_usd | quality | ts |
|---|---|---:|---:|---:|---:|---|
| `req-f5117691` | k4-challenge-s02 | 2651 | 160 | 0.002502 | 0.9 | 09:44:57.323Z |
| `req-1a418320` | k4-challenge-s04 | 2651 | 92 | 0.001488 | 0.9 | 09:44:59.982Z |
| `req-367f21d9` | k4-challenge-s03 | 2652 | 82 | 0.001335 | 0.8 | 09:45:02.641Z |
| `req-4c3cc2c4` | k4-challenge-s01 | 2651 | 150 | 0.002355 | 0.8 | 09:45:05.298Z |
| `req-1cc3af3e` | k4-challenge-s05 | 2652 | 107 | 0.001710 | 0.8 | 09:45:07.958Z |

Cùng 5 input đó sau khi tắt incident:

| correlation_id | session_id | latency_ms | tokens_out | quality |
|---|---|---:|---:|---:|
| `req-07ae748c` | k4-challenge-s01 | 150 | 84 | 0.8 |
| `req-f0a2b33d` | k4-challenge-s05 | 150 | 122 | 0.8 |
| `req-7d86a5b6` | k4-challenge-s03 | 150 | 158 | 0.8 |
| `req-1d22ff7f` | k4-challenge-s04 | 151 | 179 | 0.9 |
| `req-ee488106` | k4-challenge-s02 | 150 | 87 | 0.9 |

Đây là một **controlled experiment**: cùng 5 message, cùng feature `monitoring`, cùng concurrency 5,
cùng tiến trình API, chỉ đổi một biến duy nhất là cờ `rag_slow`. Kết quả 2651 ms ↔ 150 ms, sai khác
đúng 2500 ms, biên độ 1 ms trên 10 phép đo.

**Root cause:** bước retrieval của RAG pipeline. Trong [`app/mock_rag.py:18`](../../app/mock_rag.py#L18),
khi cờ sự cố bật thì `retrieve()` chèn `time.sleep(2.5)` trước khi tra CORPUS:

```python
def retrieve(message: str) -> list[str]:
    if STATE["tool_fail"]:
        raise RuntimeError("Vector store timeout")
    if STATE["rag_slow"]:
        time.sleep(2.5)
```

2500 ms này bám vào mọi request đi qua tầng retrieval, cộng thẳng vào `agent.run` trước khi LLM
được gọi. Nó khớp chính xác với delta 2500 ms đo được ở lớp log, và giải thích trọn vẹn tại sao
token/cost/quality/error đều không đổi.

Trong hệ thống thật, đây là hình mẫu của vector store phản hồi chậm — index quá lớn, connection pool
cạn, hoặc mạng tới vector DB xuống cấp — chứ không phải model chậm.

## 4. Phát hiện phụ: chặn event loop khuếch đại tail latency

Client đo 13300 ms cho mỗi request trong khi server chỉ log `latency_ms=2651`. Khoảng cách 5 lần này
là một sự cố thứ hai, độc lập với `rag_slow`:

- Timestamp `response_sent` trong incident cách nhau đều **2.66 s** (09:44:57.3 → 09:44:59.9 →
  09:45:02.6 → 09:45:05.3 → 09:45:07.9), dù `--concurrency 5` gửi cả 5 request cùng lúc.
- Sau khi tắt incident, chúng vẫn cách nhau đều **~0.156 s** (09:47:21.015 → .171 → .326 → .485 → .642).

Cả hai cửa sổ đều cho thấy 5 request được xử lý **nối tiếp**, không song song. Nguyên nhân:
`/chat` khai báo `async def` nhưng gọi `agent.run()` là code đồng bộ có `time.sleep()`
([`app/mock_rag.py`](../../app/mock_rag.py), [`app/mock_llm.py`](../../app/mock_llm.py)), nên nó chặn
event loop của uvicorn thay vì nhường quyền. Hệ quả là head-of-line blocking: một request chậm làm
mọi request đang chờ chậm theo, và latency người dùng thật ≈ N × latency server ghi nhận.

Đây là lý do chỉ tin `latency_ms` do server tự đo là không đủ. Header `x-response-time-ms` do
[`app/middleware.py`](../../app/middleware.py) gắn mới đo được thời gian ở tầng ngoài; nó nên được đưa
vào log và dashboard để phát hiện dạng sự cố này.

## 5. Fix action

| # | Hành động | Lớp |
|---|---|---|
| 1 | Đặt timeout cứng cho retrieval (ví dụ 500 ms) và fallback sang câu trả lời không có context kèm cảnh báo, để một vector store chậm bị cắt sớm thay vì kéo cả request. | retrieval |
| 2 | Cache kết quả retrieval theo hash của query. 5 input challenge đều thuộc feature `monitoring` và trả về cùng một document, nên cache loại bỏ gần hết lần gọi lặp. | retrieval |
| 3 | Chạy `agent.run()` trong threadpool (`await run_in_threadpool(...)`) hoặc chuyển retrieval/LLM sang client async, để một request chậm không chặn event loop. | API |
| 4 | Ghi `x-response-time-ms` (latency đo ở middleware) vào `response_sent`, để dashboard thấy được latency người dùng thật chứ không chỉ latency nội bộ của agent. | observability |

Đã xác minh cho hành động khôi phục ngay: tắt cờ sự cố đưa latency về 150–151 ms trên đúng 5 input
chính thức (bảng ở mục 3).

## 6. Preventive measure

| # | Biện pháp | Ngăn được gì |
|---|---|---|
| 1 | Giữ alert `high_latency_p95` (`p95 > 3000 ms` trong 5 phút, xem [`docs/alerts.md`](../../docs/alerts.md#alert-1)) và **bổ sung một alert cảnh báo sớm ở mức p95 > 2000 ms**, đúng `latency_threshold_ms` của challenge. Sự cố này đạt 2652 ms — vượt ngưỡng vận hành nhưng vẫn dưới SLO 3000 ms, nên alert hiện tại sẽ không bắn. | khoảng mù giữa 2000 và 3000 ms |
| 2 | Thêm span/metric latency riêng cho từng bước (retrieval, generation) thay vì chỉ đo tổng `agent.run`. Trong lần điều tra này việc khoanh vùng phải dựa vào suy luận gián tiếp (delta hằng số, `tokens_out` không tương quan); có latency per-span thì đọc trace là thấy ngay. | thời gian khoanh vùng lâu |
| 3 | Đặt SLO riêng cho dependency retrieval và alert khi p95 retrieval vượt ngưỡng, thay vì chỉ alert trên latency tổng đầu vào của người dùng. | phát hiện chậm ở tầng phụ thuộc |
| 4 | Load test hồi quy trong CI với ngưỡng p95, chạy trên tập input cố định như `data/sample_queries.jsonl`, chặn deploy nếu p95 xấu đi. | tái phát sau deploy |
| 5 | Alert trên percentile chứ không trên average, và luôn hiển thị P50 cạnh P95/P99. Sự cố này giữ P50 ở 151 ms — một dashboard chỉ có average sẽ báo "khỏe". | sự cố tail latency bị bỏ sót |

## 7. Ghi chú về evidence trace

Challenge được chạy hai lần:

1. **Lần đầu với `tracing_enabled=false`** (chưa có `LANGFUSE_*` key trong `.env`). Bằng chứng là
   correlation ID và log line thật ở mục 3; phần khoanh vùng span khi đó dựa trên suy luận gián tiếp.
2. **Lần sau với `tracing_enabled=true`**, sau khi bổ sung span `rag_retrieval` và `llm_generate`.
   Đây là nguồn của các trace ID và số liệu span ở mục 2.

Cả hai lần dùng đúng 5 input chính thức và cùng cho kết quả nhất quán: latency phát sinh ~2500 ms,
`llm_generate` không đổi. Toàn bộ trace ID trong tài liệu này lấy từ Langfuse API bằng
`api.trace.list()` / `api.trace.get()`, không có ID nào được tạo thủ công.

Lần chạy có tracing được thực hiện trong project Langfuse `My Project`
(`cmsoih1ft00mead0lcege5hq5`), là project mà thành viên phụ trách checkpoint 3 truy cập được bằng UI.
Prompt `day13-chat` v1/v2 được dựng lại trong project này theo đúng
[`PROMPT_VERSIONING.md`](../../docs/PROMPT_VERSIONING.md), nên `prompt_source=langfuse` ở mọi trace
thay vì `local-fallback`. Evidence checkpoint 2 của thành viên khác nằm ở project `VinAI_DAY13`
(`cmsoepljr00ovad0dt574axxx`) — xem [`../REPORT.md`](../REPORT.md) mục 4 để đối chiếu.

Mỗi trace trong [`challenge_traces.json`](challenge_traces.json) có sẵn trường `url` để mở trực tiếp
trên giao diện Langfuse.
