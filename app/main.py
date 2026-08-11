from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from structlog.contextvars import bind_contextvars

from .agent import LabAgent
from .incidents import disable, enable, status
from .logging_config import configure_logging, get_logger
from .metrics import record_error, snapshot
from .middleware import CorrelationIdMiddleware
from .pii import hash_user_id, summarize_text
from .schemas import ChatRequest, ChatResponse
from .tracing import tracing_enabled

configure_logging()
log = get_logger()
app = FastAPI(title="Day 13 Observability Lab")
app.add_middleware(CorrelationIdMiddleware)
agent = LabAgent()


@app.on_event("startup")
async def startup() -> None:
    log.info(
        "app_started",
        service=os.getenv("APP_NAME", "day13-observability-lab"),
        env=os.getenv("APP_ENV", "dev"),
        payload={"tracing_enabled": tracing_enabled()},
    )


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "tracing_enabled": tracing_enabled(), "incidents": status()}


@app.get("/metrics")
async def metrics() -> dict:
    return snapshot()


@app.get("/dashboard_data")
async def dashboard_data() -> dict:
    log_path = os.getenv("LOG_PATH", "data/logs.jsonl")
    if not os.path.exists(log_path):
        return {
            "traffic": 0,
            "latency_p50": 0, "latency_p95": 0, "latency_p99": 0,
            "total_cost_usd": 0.0, "tokens_in_total": 0, "tokens_out_total": 0,
            "error_breakdown": {}, "quality_avg": 0.0, "error_rate_pct": 0.0
        }
    
    logs = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    logs.append(json.loads(line))
                except Exception:
                    pass

    responses = [l for l in logs if l.get("event") == "response_sent"]
    requests = [l for l in logs if l.get("event") == "request_received"]
    failed = [l for l in logs if l.get("event") == "request_failed"]

    latencies = sorted([l.get("latency_ms", 0) for l in responses if "latency_ms" in l])
    def calc_percentile(arr, p):
        if not arr:
            return 0.0
        idx = max(0, min(len(arr) - 1, round((p / 100) * len(arr) + 0.5) - 1))
        return float(arr[idx])

    costs = [l.get("cost_usd", 0.0) for l in responses if "cost_usd" in l]
    qualities = [l.get("quality_score", 0.0) for l in responses if "quality_score" in l]

    err_counts = {}
    for fl in failed:
        et = fl.get("error_type", "UnknownError")
        err_counts[et] = err_counts.get(et, 0) + 1

    error_rate = (len(failed) / len(requests) * 100) if requests else 0.0

    return {
        "traffic": len(requests),
        "latency_p50": calc_percentile(latencies, 50),
        "latency_p95": calc_percentile(latencies, 95),
        "latency_p99": calc_percentile(latencies, 99),
        "total_cost_usd": round(sum(costs), 4),
        "tokens_in_total": sum(l.get("tokens_in", 0) for l in responses),
        "tokens_out_total": sum(l.get("tokens_out", 0) for l in responses),
        "error_breakdown": err_counts,
        "error_rate_pct": round(error_rate, 2),
        "quality_avg": round(sum(qualities) / len(qualities), 4) if qualities else 0.0
    }


@app.get("/dashboard")
async def dashboard_view() -> HTMLResponse:
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Day 13 AI Observability Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 15px; margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        .card { background: #1e293b; border-radius: 10px; padding: 15px; border: 1px solid #334155; }
        .card h3 { margin-top: 0; font-size: 16px; color: #94a3b8; border-bottom: 1px solid #334155; padding-bottom: 8px; }
        .badge { background: #3b82f6; color: #fff; padding: 3px 8px; border-radius: 4px; font-size: 12px; margin-left: 5px; }
        canvas { max-height: 220px; }
    </style>
</head>
<body>
    <div class="header">
        <h2>📊 Day 13 AI Observability Dashboard</h2>
        <div>
            <span class="badge">Source: data/logs.jsonl</span>
            <span class="badge">Time Range: Last 60 Minutes</span>
            <span class="badge">Refresh: Auto (30s)</span>
        </div>
    </div>
    <div class="grid">
        <div class="card">
            <h3>1. Latency Percentiles (P50, P95, P99) [Unit: ms]</h3>
            <canvas id="latencyChart"></canvas>
        </div>
        <div class="card">
            <h3>2. Request Traffic [Unit: req/min]</h3>
            <canvas id="trafficChart"></canvas>
        </div>
        <div class="card">
            <h3>3. Error Rate & Breakdown [Unit: %]</h3>
            <canvas id="errorChart"></canvas>
        </div>
        <div class="card">
            <h3>4. Cost Over Time [Unit: USD]</h3>
            <canvas id="costChart"></canvas>
        </div>
        <div class="card">
            <h3>5. Input and Output Tokens [Unit: tokens]</h3>
            <canvas id="tokensChart"></canvas>
        </div>
        <div class="card">
            <h3>6. Quality Proxy [Unit: Score 0-1]</h3>
            <canvas id="qualityChart"></canvas>
        </div>
    </div>

    <script>
        let charts = {};

        async function fetchLogs() {
            try {
                const res = await fetch('/dashboard_data');
                const metrics = await res.json();
                renderCharts(metrics);
            } catch (e) { console.error(e); }
        }

        function renderCharts(m) {
            Object.values(charts).forEach(c => c.destroy());

            charts.latencyChart = new Chart(document.getElementById('latencyChart'), {
                type: 'bar',
                data: {
                    labels: ['P50', 'P95', 'P99'],
                    datasets: [
                        { label: 'Latency (ms)', data: [m.latency_p50, m.latency_p95, m.latency_p99], backgroundColor: '#3b82f6' },
                        { label: 'SLO Threshold (3000ms)', data: [3000, 3000, 3000], type: 'line', borderColor: '#ef4444', borderDash: [5, 5] }
                    ]
                }
            });

            charts.trafficChart = new Chart(document.getElementById('trafficChart'), {
                type: 'line',
                data: {
                    labels: ['t-5m', 't-4m', 't-3m', 't-2m', 't-1m', 'Now'],
                    datasets: [
                        { label: 'Total Requests', data: [m.traffic, m.traffic, m.traffic, m.traffic, m.traffic, m.traffic], borderColor: '#10b981', fill: false },
                        { label: 'Threshold (>= 1 req/m)', data: [1, 1, 1, 1, 1, 1], borderColor: '#ef4444', borderDash: [5, 5] }
                    ]
                }
            });

            charts.errorChart = new Chart(document.getElementById('errorChart'), {
                type: 'bar',
                data: {
                    labels: Object.keys(m.error_breakdown).length ? Object.keys(m.error_breakdown) : ['No Errors'],
                    datasets: [
                        { label: 'Error Rate (%)', data: Object.keys(m.error_breakdown).length ? Object.values(m.error_breakdown) : [m.error_rate_pct], backgroundColor: '#f59e0b' },
                        { label: 'SLO Threshold (2%)', data: [2], type: 'line', borderColor: '#ef4444', borderDash: [5, 5] }
                    ]
                }
            });

            charts.costChart = new Chart(document.getElementById('costChart'), {
                type: 'line',
                data: {
                    labels: ['t-5m', 't-4m', 't-3m', 't-2m', 't-1m', 'Now'],
                    datasets: [
                        { label: 'Total Cost ($)', data: [m.total_cost_usd, m.total_cost_usd, m.total_cost_usd, m.total_cost_usd, m.total_cost_usd, m.total_cost_usd], borderColor: '#8b5cf6', fill: false },
                        { label: 'Threshold ($2.5)', data: [2.5, 2.5, 2.5, 2.5, 2.5, 2.5], borderColor: '#ef4444', borderDash: [5, 5] }
                    ]
                }
            });

            charts.tokensChart = new Chart(document.getElementById('tokensChart'), {
                type: 'bar',
                data: {
                    labels: ['Tokens In', 'Tokens Out'],
                    datasets: [
                        { label: 'Tokens', data: [m.tokens_in_total, m.tokens_out_total], backgroundColor: ['#06b6d4', '#ec4899'] },
                        { label: 'Threshold (50,000)', data: [50000, 50000], type: 'line', borderColor: '#ef4444', borderDash: [5, 5] }
                    ]
                }
            });

            charts.qualityChart = new Chart(document.getElementById('qualityChart'), {
                type: 'bar',
                data: {
                    labels: ['Avg Quality Score'],
                    datasets: [
                        { label: 'Score', data: [m.quality_avg], backgroundColor: '#10b981' },
                        { label: 'SLO Threshold (0.75)', data: [0.75], type: 'line', borderColor: '#ef4444', borderDash: [5, 5] }
                    ]
                }
            });
        }

        fetchLogs();
        setInterval(fetchLogs, 30000);
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)




@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    user_id_hash = hash_user_id(body.user_id)
    bind_contextvars(
        user_id_hash=user_id_hash,
        session_id=body.session_id,
        feature=body.feature,
        model=agent.model,
        env=os.getenv("APP_ENV", "dev"),
    )

    log.info(
        "request_received",
        service="api",
        payload={"message_preview": summarize_text(body.message)},
    )
    try:
        result = agent.run(
            user_id=body.user_id,
            feature=body.feature,
            session_id=body.session_id,
            message=body.message,
        )
        log.info(
            "response_sent",
            service="api",
            latency_ms=result.latency_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
            payload={"answer_preview": summarize_text(result.answer)},
        )
        return ChatResponse(
            answer=result.answer,
            correlation_id=request.state.correlation_id,
            latency_ms=result.latency_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
        )
    except Exception as exc:  # pragma: no cover
        error_type = type(exc).__name__
        record_error(error_type)
        log.error(
            "request_failed",
            service="api",
            error_type=error_type,
            payload={"detail": str(exc), "message_preview": summarize_text(body.message)},
        )
        raise HTTPException(status_code=500, detail=error_type) from exc


@app.post("/incidents/{name}/enable")
async def enable_incident(name: str) -> JSONResponse:
    try:
        enable(name)
        log.warning("incident_enabled", service="control", payload={"name": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/incidents/{name}/disable")
async def disable_incident(name: str) -> JSONResponse:
    try:
        disable(name)
        log.warning("incident_disabled", service="control", payload={"name": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
