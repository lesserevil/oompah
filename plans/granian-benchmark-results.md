# Granian benchmark results

## Benchmark run: 2026-06-09 15:57 (canonical, 20 concurrency)

**Environment:** Python 3.12.12 · uvicorn 0.41.0 · granian 2.7.5 · CPU: AMD Ryzen Threadripper 3970X 32-Core Processor
**Duration per server:** 20s  **Concurrency:** 20
**Workload mix:** 60% /api/v1/state · 30% / · 10% /favicon.ico

+---------+--------+---------+--------+--------+--------+--------+
| server  | req/s  | mean ms | p50 ms | p90 ms | p99 ms | errors |
+---------+--------+---------+--------+--------+--------+--------+
| uvicorn | 2528.0 | 7.9     | 7.5    | 8.8    | 12.0   | 0      |
| granian | 2581.7 | 7.7     | 7.5    | 8.3    | 10.6   | 0      |
+---------+--------+---------+--------+--------+--------+--------+

Total requests — uvicorn: 50,560 · granian: 51,633
Throughput delta (granian vs uvicorn): **+2.1%**
p99 latency delta: **-11.8%** (granian is tighter)

## Benchmark run: 2026-06-09 15:56 (10 concurrency)

**Environment:** Python 3.12.12 · uvicorn 0.41.0 · granian 2.7.5 · CPU: AMD Ryzen Threadripper 3970X 32-Core Processor
**Duration per server:** 15s  **Concurrency:** 10
**Workload mix:** 60% /api/v1/state · 30% / · 10% /favicon.ico

+---------+--------+---------+--------+--------+--------+--------+
| server  | req/s  | mean ms | p50 ms | p90 ms | p99 ms | errors |
+---------+--------+---------+--------+--------+--------+--------+
| uvicorn | 2439.3 | 4.1     | 4.0    | 4.5    | 5.9    | 0      |
| granian | 2412.0 | 4.1     | 4.1    | 4.5    | 5.9    | 0      |
+---------+--------+---------+--------+--------+--------+--------+

Total requests — uvicorn: 36,590 · granian: 36,180
Throughput delta (granian vs uvicorn): **-1.1%** (within noise)
p99 latency delta: **-1.0%** (within noise)

---

## Analysis and go/no-go decision

### What the numbers say

Both runs used a representative mixed workload mirroring the oompah dashboard's
real traffic pattern (frequent `/api/v1/state` polls, periodic full-page HTML,
occasional static fetches). Results:

| concurrency | granian rps delta | granian p99 delta |
|-------------|-------------------|-------------------|
| 10 workers  | -1.1% (noise)     | -1.0% (noise)     |
| 20 workers  | +2.1%             | -11.8%            |

At low concurrency the two servers are statistically indistinguishable.
At higher concurrency granian shows a small throughput edge and a more
meaningful tail-latency improvement (-12% p99). Both are well below the
+22–25% throughput gain reported in doc-1's isolated `/` route micro-benchmark.

The discrepancy is expected: the isolated benchmark used a tiny cached
response on a single route; the representative workload includes larger
HTML payloads (~6 kB) across multiple routes, which exposes payload
serialization and async handler overhead that is common to both servers.

### Why the real-world gain is smaller than the micro-benchmark

1. **Payload size dominates at high throughput.** Granian's wire efficiency
   advantage is most visible for trivial responses; larger payloads shift
   cost into Python's memory copy/response serialisation path, which both
   servers share.
2. **Route overhead.** oompah's routes do `JSONResponse(snapshot)` /
   `HTMLResponse(content)` rather than ultra-minimal raw ASGI responses;
   FastAPI's middleware and ASGI adapter consume a similar fraction of
   handler time under both servers.
3. **Event-loop coupling.** In production, the shared event loop also runs
   the orchestrator, watchfiles watcher, and WebSocket fan-out. Those
   coroutines compete for loop time regardless of server; a pure HTTP
   benchmark misses this.

### Decision: **NO-GO** for making granian the default

**Granian stays opt-in behind `--server granian`.** Rationale:

1. **HTTP is not the bottleneck.** oompah's latency budget is dominated by
   LLM round-trips (seconds) and orchestrator ticks (100 ms–2 s). A 2%
   HTTP throughput gain is invisible to end users.
2. **Multi-worker is locked out.** Granian's biggest win (multi-worker Tokio)
   cannot be used because the app holds shared in-process state
   (`_orchestrator`, `_ws_clients`). Until the orchestrator is decoupled
   (TASK-473.4), granian is a single-worker drop-in with marginal benefit.
3. **Hardening prerequisites outstanding.** TASK-472.1–TASK-472.7 (lifespan
   abort, restart relay, WS validation, multipart/static/Jinja validation,
   automated tests, docs) must be complete before any production default
   switch.
4. **Risk/reward ratio unfavourable.** Changing the default server is a
   high-visibility, production-impacting change; the measured performance
   gain does not justify the operational risk right now.

### When to re-evaluate

Re-run this benchmark and reconsider after:
- TASK-472.1–472.7 are merged (granian fully hardened and tested)
- TASK-473 event-loop contention epic is complete (blocking work off loop)
- TASK-473.4 orchestrator decoupling spike: if successful, multi-worker
  granian becomes possible, and the throughput gains will be multiplicative

At that point the benchmark should be re-run with the real oompah app (not
the synthetic app used here) under production-representative load.
