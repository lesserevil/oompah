#!/usr/bin/env python3
"""Profile oompah HTTP/WebSocket latency under mixed workload.

Measures end-to-end request latency for a representative set of routes and
breaks down where time is actually spent:

  - HTTP/network layer  — measured via the favicon route (pure bytes, no logic)
  - State API overhead  — difference between /api/v1/state and favicon
  - Issues API overhead — difference between /api/v1/issues and state API
  - Orchestrator layer  — tick and dispatch durations from server-side metrics

After the load test the script fetches server-side ``api_metrics`` and
``orchestrator_metrics`` from ``/api/v1/state`` to cross-validate with the
client-side timings and identify the dominant bottleneck.

Usage::

    uv run scripts/bench_server.py                 # defaults
    uv run scripts/bench_server.py --concurrency 20 --duration 60
    uv run scripts/bench_server.py --url http://10.0.0.1:8090 --json

Requires the oompah server to be running (``make start``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field

import httpx

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_URL = "http://127.0.0.1:8090"
DEFAULT_CONCURRENCY = 10
DEFAULT_DURATION_S = 30
DEFAULT_WARMUP_S = 5

# Routes included in the mixed workload.
# Order matters: favicon first so it is used as the HTTP-only baseline.
ROUTES: list[tuple[str, str]] = [
    ("favicon (HTTP-only)", "/favicon.ico"),
    ("state API", "/api/v1/state"),
    ("issues API", "/api/v1/issues"),
    ("dashboard HTML", "/"),
]


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


def percentile(data: list[float], pct: float) -> float:
    """Return the *pct*-th percentile of *data* (linear interpolation).

    Parameters
    ----------
    data:
        Non-empty list of float values.
    pct:
        Percentile in the range ``[0, 100]``.

    Returns ``0.0`` for an empty list.
    """
    if not data:
        return 0.0
    if not (0.0 <= pct <= 100.0):
        raise ValueError(f"pct must be in [0, 100], got {pct}")
    sorted_data = sorted(data)
    idx = (pct / 100.0) * (len(sorted_data) - 1)
    lower = int(idx)
    upper = lower + 1
    if upper >= len(sorted_data):
        return sorted_data[-1]
    frac = idx - lower
    return sorted_data[lower] + frac * (sorted_data[upper] - sorted_data[lower])


@dataclass
class RouteResult:
    """Accumulated timing samples for a single route."""

    route: str
    path: str
    latencies_ms: list[float] = field(default_factory=list)
    error_count: int = 0

    # ------------------------------------------------------------------
    # Computed statistics
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Number of successful samples."""
        return len(self.latencies_ms)

    def mean(self) -> float:
        """Arithmetic mean latency (ms)."""
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

    def p50(self) -> float:
        """Median latency (ms)."""
        return percentile(self.latencies_ms, 50)

    def p90(self) -> float:
        """90th-percentile latency (ms)."""
        return percentile(self.latencies_ms, 90)

    def p95(self) -> float:
        """95th-percentile latency (ms)."""
        return percentile(self.latencies_ms, 95)

    def p99(self) -> float:
        """99th-percentile latency (ms)."""
        return percentile(self.latencies_ms, 99)

    def to_dict(self) -> dict:
        """Serialise to a plain dict (for JSON output)."""
        return {
            "count": self.count(),
            "mean_ms": round(self.mean(), 3),
            "p50_ms": round(self.p50(), 3),
            "p90_ms": round(self.p90(), 3),
            "p95_ms": round(self.p95(), 3),
            "p99_ms": round(self.p99(), 3),
            "error_count": self.error_count,
        }


# ---------------------------------------------------------------------------
# Async worker
# ---------------------------------------------------------------------------


async def _worker(
    client: httpx.AsyncClient,
    base_url: str,
    results: dict[str, RouteResult],
    stop_event: asyncio.Event,
) -> None:
    """Send GET requests in round-robin across all routes until *stop_event*."""
    route_names = list(results.keys())
    idx = 0
    while not stop_event.is_set():
        name = route_names[idx % len(route_names)]
        idx += 1
        result = results[name]
        url = base_url + result.path
        t0 = time.monotonic()
        try:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            result.latencies_ms.append(elapsed_ms)
        except Exception:
            result.error_count += 1


# ---------------------------------------------------------------------------
# Benchmark driver
# ---------------------------------------------------------------------------


async def run_benchmark(
    base_url: str,
    concurrency: int,
    duration_s: float,
    warmup_s: float,
) -> tuple[dict[str, RouteResult], dict]:
    """Run the mixed workload benchmark and return results.

    Returns
    -------
    results:
        Mapping of route name → :class:`RouteResult`.
    server_metrics:
        Dict with ``api_metrics`` and ``orchestrator_metrics`` pulled from the
        server after the load test; empty dict if the server is unreachable.
    """
    results: dict[str, RouteResult] = {
        name: RouteResult(route=name, path=path) for name, path in ROUTES
    }

    limits = httpx.Limits(
        max_connections=concurrency + 10,
        max_keepalive_connections=concurrency,
    )
    async with httpx.AsyncClient(base_url=base_url, limits=limits) as client:

        # --- Warmup phase ---
        if warmup_s > 0:
            print(f"  Warming up for {warmup_s:.0f}s …", flush=True)
            stop_warmup = asyncio.Event()
            warmup_tasks = [
                asyncio.create_task(_worker(client, base_url, results, stop_warmup))
                for _ in range(concurrency)
            ]
            await asyncio.sleep(warmup_s)
            stop_warmup.set()
            await asyncio.gather(*warmup_tasks, return_exceptions=True)
            # Discard warmup data so the report reflects steady-state.
            for r in results.values():
                r.latencies_ms.clear()
                r.error_count = 0

        # --- Load phase ---
        print(
            f"  Running load test ({concurrency} workers × {duration_s:.0f}s) …",
            flush=True,
        )
        stop_load = asyncio.Event()
        load_tasks = [
            asyncio.create_task(_worker(client, base_url, results, stop_load))
            for _ in range(concurrency)
        ]
        await asyncio.sleep(duration_s)
        stop_load.set()
        await asyncio.gather(*load_tasks, return_exceptions=True)

        # --- Collect server-side metrics from the state endpoint ---
        server_metrics: dict = {}
        try:
            resp = await client.get("/api/v1/state", timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                server_metrics["api_metrics"] = data.get("api_metrics", {})
                server_metrics["orchestrator_metrics"] = data.get(
                    "orchestrator_metrics", {}
                )
        except Exception as exc:
            print(f"  Warning: could not collect server-side metrics: {exc}", flush=True)

    return results, server_metrics


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def _ms(v: float) -> str:
    return f"{v:7.1f}ms"


def print_report(
    results: dict[str, RouteResult],
    server_metrics: dict,
    base_url: str,
) -> None:
    """Print a human-readable latency breakdown report."""
    width = 70
    print("\n" + "=" * width)
    print(f"  OOMPAH REQUEST LATENCY PROFILE  —  {base_url}")
    print("=" * width)

    # ---- Per-route latency table ----------------------------------------
    print("\n── Client-side per-route latency ──\n")
    hdr = (
        f"  {'Route':<28}  {'N':>5}  {'mean':>8}  {'p50':>8}"
        f"  {'p90':>8}  {'p95':>8}  {'p99':>8}  err"
    )
    print(hdr)
    print("  " + "─" * (len(hdr) - 2))

    for name, r in results.items():
        if r.count() == 0:
            print(f"  {name:<28}  {'—':>5}")
            continue
        print(
            f"  {name:<28}  {r.count():>5}"
            f"  {_ms(r.mean())}  {_ms(r.p50())}"
            f"  {_ms(r.p90())}  {_ms(r.p95())}  {_ms(r.p99())}"
            f"  {r.error_count}"
        )

    # ---- Layer breakdown (derived from client measurements) -------------
    favicon = results.get("favicon (HTTP-only)")
    state = results.get("state API")
    issues = results.get("issues API")

    if favicon and state and favicon.count() > 0 and state.count() > 0:
        print("\n── Layer breakdown (p50, client-side) ──\n")
        http_p50 = favicon.p50()
        state_p50 = state.p50()
        issues_p50 = issues.p50() if (issues and issues.count() > 0) else None

        state_delta = max(0.0, state_p50 - http_p50)
        print(f"  HTTP/network overhead (favicon baseline): {_ms(http_p50)}")
        print(f"  State-API serialisation delta:            {_ms(state_delta)}")
        if issues_p50 is not None:
            issues_delta = max(0.0, issues_p50 - state_p50)
            print(f"  Issues-snapshot delta (vs state):         {_ms(issues_delta)}")

    # ---- Server-side API metrics ----------------------------------------
    api_metrics = server_metrics.get("api_metrics", {})
    if api_metrics:
        print("\n── Server-side API metrics (from /api/v1/state) ──\n")
        for endpoint, stats in sorted(api_metrics.items()):
            print(
                f"  {endpoint:<38}"
                f"  n={stats.get('count', 0):>6}"
                f"  avg={_ms(stats.get('avg_ms', 0))}"
                f"  last={_ms(stats.get('last_ms', 0))}"
                f"  max={_ms(stats.get('max_ms', 0))}"
                f"  slow={stats.get('slow_count', 0)}"
            )

    # ---- Orchestrator metrics -------------------------------------------
    orch = server_metrics.get("orchestrator_metrics", {})
    if orch:
        print("\n── Orchestrator metrics (from server) ──\n")

        last_tick: dict = orch.get("last_tick") or {}
        if last_tick:
            tick_total_ms = float(
                last_tick.get("total_tick_ms", last_tick.get("total_ms", 0))
            )
            print(f"  Last tick total:  {_ms(tick_total_ms)}")
            for k, v in sorted(last_tick.items()):
                if k.endswith("_ms") and k not in ("total_tick_ms", "total_ms"):
                    print(f"    {k:<42} {_ms(float(v))}")

        last_dispatch: dict = orch.get("last_dispatch") or {}
        if last_dispatch:
            dispatch_total_ms = float(last_dispatch.get("total_ms", 0))
            print(f"\n  Last dispatch total:  {_ms(dispatch_total_ms)}")
            for k, v in sorted(last_dispatch.items()):
                if k.endswith("_ms"):
                    print(f"    {k:<42} {_ms(float(v))}")

    # ---- Bottleneck conclusion ------------------------------------------
    print("\n── Bottleneck summary ──\n")

    favicon_p95 = favicon.p95() if (favicon and favicon.count() > 0) else 0.0
    state_p95 = state.p95() if (state and state.count() > 0) else 0.0

    if favicon_p95 > 0 and state_p95 > 0:
        http_share = favicon_p95 / state_p95 * 100.0
        orch_share = max(0.0, 100.0 - http_share)
        print(
            f"  At p95: HTTP/network = {http_share:.1f}%  |"
            f"  orchestrator/state = {orch_share:.1f}%"
            f"  (of /api/v1/state latency)"
        )

    tick_ms = 0.0
    last_tick = orch.get("last_tick") or {}
    if last_tick:
        tick_ms = float(last_tick.get("total_tick_ms", last_tick.get("total_ms", 0)))

    if tick_ms > 500:
        print(f"  ⚠  Orchestrator tick = {_ms(tick_ms)} — GIL/blocking work is likely")
        print("     stalling the event loop and inflating p99+ latencies.")
    elif tick_ms > 100:
        print(f"  ⚠  Orchestrator tick = {_ms(tick_ms)} — occasional event-loop stalls")
        print("     possible; watch p99 under heavier load.")
    elif tick_ms > 0:
        print(f"  ✓  Orchestrator tick = {_ms(tick_ms)} — within acceptable range.")
    else:
        print(
            "  (No orchestrator tick data — server may be idle or not yet ticked.)"
        )

    print("\n" + "=" * width + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Profile oompah HTTP latency under a mixed workload.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Server base URL (default: {DEFAULT_URL})",
    )
    p.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Number of concurrent workers (default: {DEFAULT_CONCURRENCY})",
    )
    p.add_argument(
        "--duration",
        "-d",
        type=float,
        default=DEFAULT_DURATION_S,
        help=f"Load-test duration in seconds (default: {DEFAULT_DURATION_S})",
    )
    p.add_argument(
        "--warmup",
        "-w",
        type=float,
        default=DEFAULT_WARMUP_S,
        help=f"Warmup duration in seconds (default: {DEFAULT_WARMUP_S})",
    )
    p.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Emit raw JSON instead of the human-readable report",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    base_url = args.url.rstrip("/")

    print(f"\noompah latency profiler")
    print(f"  URL:         {base_url}")
    print(f"  Concurrency: {args.concurrency} workers")
    print(f"  Warmup:      {args.warmup:.0f}s")
    print(f"  Duration:    {args.duration:.0f}s")

    # Quick connectivity check before committing to a long run.
    try:
        with httpx.Client(timeout=5.0) as chk:
            chk.get(f"{base_url}/favicon.ico").raise_for_status()
    except Exception as exc:
        print(f"\nERROR: cannot reach {base_url} — {exc}")
        print("       Make sure oompah is running (make start).")
        sys.exit(1)

    results, server_metrics = asyncio.run(
        run_benchmark(base_url, args.concurrency, args.duration, args.warmup)
    )

    if args.output_json:
        out = {
            "url": base_url,
            "concurrency": args.concurrency,
            "duration_s": args.duration,
            "routes": {name: r.to_dict() for name, r in results.items()},
            "server_metrics": server_metrics,
        }
        print(json.dumps(out, indent=2))
    else:
        print_report(results, server_metrics, base_url)


if __name__ == "__main__":
    main()
