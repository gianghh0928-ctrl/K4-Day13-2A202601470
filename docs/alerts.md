# Alert và Runbook

Mỗi alert dưới đây dựa trên triệu chứng người dùng cảm nhận được hoặc SLO trong
[`config/slo.yaml`](../config/slo.yaml), không dựa vào tên implementation nội bộ (ví dụ không alert trên
`STATE["rag_slow"]`). Định nghĩa máy đọc được nằm trong [`config/alert_rules.yaml`](../config/alert_rules.yaml).

Nguồn dữ liệu chung của cả ba alert là `data/logs.jsonl` theo mapping event/field trong
[DASHBOARD_SETUP.md](DASHBOARD_SETUP.md); cửa sổ đánh giá là 60 phút gần nhất giống dashboard.

## Alert 1

- Tên: `high_latency_p95`
- Severity: critical
- SLI/SLO liên quan: `latency_p95_ms` — objective 3000 ms, target 99.5% trong 28 ngày
- Điều kiện và thời gian duy trì: `p95(response_sent.latency_ms) > 3000` duy trì 5 phút
- Ảnh hưởng tới người dùng: câu trả lời về chậm hơn 3 giây; phần đuôi phân phối (P95/P99) là nhóm
  người dùng chờ lâu nhất và dễ bỏ request giữa chừng. Average latency có thể vẫn "bình thường" nên
  alert phải đặt trên percentile.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel `latency` để xác định thời điểm P95 bắt đầu vượt ngưỡng, đối chiếu panel `traffic` xem
     latency tăng có đi kèm traffic tăng hay không (nếu không, nghi ngờ một span cụ thể chậm).
  2. Mở một trace trong khoảng đó trên Langfuse và so sánh thời lượng các span: retrieval (`mock_rag.retrieve`)
     so với generation (`FakeLLM.generate`). Ghi lại trace ID của trace chậm nhất.
  3. Lọc `data/logs.jsonl` theo `correlation_id` của request chậm, so `latency_ms` của `response_sent`
     với baseline (~1150 ms) để xác nhận độ chênh khớp với span nghi vấn.
- Mitigation tạm thời: bật cache cho tầng retrieval và đặt timeout cứng cho vector store để request
  fail nhanh và fallback thay vì treo; nếu nguyên nhân ở phía LLM thì giảm `max_tokens` hoặc chuyển
  sang model nhanh hơn cho `feature` bị ảnh hưởng.
- Owner: oncall-eng

## Alert 2

- Tên: `high_error_rate`
- Severity: critical
- SLI/SLO liên quan: `error_rate_pct` — objective 2%, target 99.0% trong 28 ngày
- Điều kiện và thời gian duy trì: `count(request_failed) / count(request_received) * 100 > 2.0`
  duy trì 3 phút (cửa sổ ngắn hơn Alert 1 vì lỗi ảnh hưởng người dùng ngay lập tức)
- Ảnh hưởng tới người dùng: request trả HTTP 500 và người dùng không nhận được câu trả lời nào.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel `errors` xem `count_by_value(error_type)` để biết lỗi tập trung ở loại nào
     (ví dụ `RuntimeError` từ vector store so với lỗi validation).
  2. Lấy `correlation_id` của một `request_failed` và đọc `payload.detail` trong log để biết
     component nào raise exception.
  3. Kiểm tra trạng thái dependency ngoài (vector store, Langfuse, LLM upstream) và xem lần deploy
     hoặc lần đổi label prompt gần nhất có trùng thời điểm error rate tăng không.
- Mitigation tạm thời: bật circuit breaker cho dependency đang lỗi và trả fallback answer có kèm
  cảnh báo giảm chất lượng, thay vì để toàn bộ request 500; nếu lỗi bắt đầu ngay sau một deploy thì
  rollback deploy đó.
- Owner: oncall-eng

## Alert 3

- Tên: `low_quality_score`
- Severity: warning
- SLI/SLO liên quan: `quality_score_avg` — objective 0.75, target 95% trong 28 ngày
- Điều kiện và thời gian duy trì: `mean(response_sent.quality_score) < 0.75` duy trì 5 phút
- Ảnh hưởng tới người dùng: hệ thống vẫn trả 200 và vẫn nhanh, nhưng nội dung câu trả lời kém —
  đây là dạng lỗi "im lặng" mà latency và error rate không phát hiện được. Severity là warning vì
  service chưa down; cần người xử lý trong giờ làm việc chứ không cần gọi đêm.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel `quality` xác định thời điểm mean tụt, rồi so với thời điểm đổi label `production`
     của prompt `day13-chat`.
  2. Mở trace của các request điểm thấp, đọc metadata `prompt_name` / `prompt_label` /
     `prompt_version` để biết chính xác request đó dùng version nào, và `prompt_source` để loại trừ
     trường hợp app đang chạy `local-fallback` do fetch prompt lỗi.
  3. Kiểm tra metadata `doc_count` của span retrieval: `doc_count` thấp hoặc docs không khớp domain
     nghĩa là vấn đề ở retrieval chứ không phải ở prompt.
- Mitigation tạm thời: rollback label `production` của prompt `day13-chat` về version 1 theo
  [PROMPT_VERSIONING.md](PROMPT_VERSIONING.md), sau đó chạy lại cùng input để xác nhận
  `quality_score` hồi phục trước khi điều tra tiếp version mới.
- Owner: oncall-eng

## Ghi chú thiết kế

- Ba alert phủ ba nhóm triệu chứng khác nhau: chậm (latency), lỗi hẳn (error rate) và sai âm thầm
  (quality). Cost không được đặt alert paging riêng vì vượt ngân sách không làm gián đoạn người dùng;
  panel `cost` với threshold tổng 2.5 USD dùng để review theo ngày.
- Mọi alert đều có duration để tránh bắn cảnh báo vì một spike đơn lẻ, và đều có owner rõ ràng để
  alert không rơi vào trạng thái không ai nhận.
