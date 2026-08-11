from __future__ import annotations

import time

from .incidents import STATE
from .tracing import observe

CORPUS = {
    "refund": ["Refunds are available within 7 days with proof of purchase."],
    "monitoring": ["Metrics detect incidents, traces localize them, logs explain root cause."],
    "policy": ["Do not expose PII in logs. Use sanitized summaries only."],
}


# Span riêng cho tầng retrieval: nếu chỉ đo tổng thời gian của LabAgent.run thì không tách được
# retrieval chậm với LLM chậm, và việc khoanh vùng phải suy luận gián tiếp.
# capture_input=False vì `message` là input thô của người dùng và có thể chứa PII; giữ đúng policy
# mà LabAgent.run đang dùng, không gửi nội dung chưa scrub sang Langfuse.
@observe(name="rag_retrieval", capture_input=False)
def retrieve(message: str) -> list[str]:
    if STATE["tool_fail"]:
        raise RuntimeError("Vector store timeout")
    if STATE["rag_slow"]:
        time.sleep(2.5)
    lowered = message.lower()
    for key, docs in CORPUS.items():
        if key in lowered:
            return docs
    return ["No domain document matched. Use general fallback answer."]
