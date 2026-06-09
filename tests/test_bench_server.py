"""Unit tests for scripts/bench_server.py helpers.

Tests cover the statistics helpers (``percentile``, ``RouteResult``) and
the report / CLI plumbing without requiring a running server.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the script as a module (it lives outside the package)
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "bench_server.py"


def _load_bench_module():
    """Dynamically import scripts/bench_server.py as a module.

    The module must be registered in sys.modules *before* exec_module so that
    Python's dataclass machinery can resolve the ``__module__`` attribute of
    ``RouteResult`` back to the actual module dict.
    """
    spec = importlib.util.spec_from_file_location("bench_server", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass __module__ lookup works.
    sys.modules["bench_server"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bench():
    """Return the bench_server module."""
    return _load_bench_module()


# ---------------------------------------------------------------------------
# percentile()
# ---------------------------------------------------------------------------


class TestPercentile:
    def test_empty_returns_zero(self, bench):
        assert bench.percentile([], 50) == 0.0

    def test_single_element(self, bench):
        assert bench.percentile([42.0], 0) == 42.0
        assert bench.percentile([42.0], 50) == 42.0
        assert bench.percentile([42.0], 100) == 42.0

    def test_p50_even_list(self, bench):
        # [1, 2, 3, 4] → median is 2.5
        result = bench.percentile([1.0, 2.0, 3.0, 4.0], 50)
        assert result == pytest.approx(2.5, rel=1e-6)

    def test_p50_odd_list(self, bench):
        result = bench.percentile([1.0, 2.0, 3.0], 50)
        assert result == pytest.approx(2.0, rel=1e-6)

    def test_p0_is_min(self, bench):
        data = [5.0, 1.0, 3.0, 9.0, 2.0]
        assert bench.percentile(data, 0) == pytest.approx(1.0, rel=1e-6)

    def test_p100_is_max(self, bench):
        data = [5.0, 1.0, 3.0, 9.0, 2.0]
        assert bench.percentile(data, 100) == pytest.approx(9.0, rel=1e-6)

    def test_p90_interpolation(self, bench):
        # 10 elements [1..10]: p90 index = 0.9 * 9 = 8.1 → 9 + 0.1*(10-9) = 9.1
        data = list(range(1, 11))  # [1, 2, ..., 10]
        result = bench.percentile([float(x) for x in data], 90)
        assert result == pytest.approx(9.1, rel=1e-6)

    def test_unsorted_input(self, bench):
        data = [10.0, 3.0, 7.0, 1.0, 5.0]
        # sorted: [1, 3, 5, 7, 10]
        assert bench.percentile(data, 0) == pytest.approx(1.0, rel=1e-6)
        assert bench.percentile(data, 100) == pytest.approx(10.0, rel=1e-6)

    def test_invalid_pct_raises(self, bench):
        with pytest.raises(ValueError):
            bench.percentile([1.0], -1)
        with pytest.raises(ValueError):
            bench.percentile([1.0], 101)

    def test_identical_values(self, bench):
        data = [5.0] * 100
        for pct in (0, 25, 50, 75, 99, 100):
            assert bench.percentile(data, pct) == pytest.approx(5.0, rel=1e-6)


# ---------------------------------------------------------------------------
# RouteResult
# ---------------------------------------------------------------------------


class TestRouteResult:
    def _make(self, bench, latencies=None, errors=0):
        r = bench.RouteResult(route="test", path="/test")
        if latencies:
            r.latencies_ms = list(latencies)
        r.error_count = errors
        return r

    def test_empty_result(self, bench):
        r = self._make(bench)
        assert r.count() == 0
        assert r.mean() == 0.0
        assert r.p50() == 0.0
        assert r.p90() == 0.0
        assert r.p95() == 0.0
        assert r.p99() == 0.0

    def test_count(self, bench):
        r = self._make(bench, [1.0, 2.0, 3.0])
        assert r.count() == 3

    def test_mean(self, bench):
        r = self._make(bench, [10.0, 20.0, 30.0])
        assert r.mean() == pytest.approx(20.0, rel=1e-6)

    def test_p50_delegates_to_percentile(self, bench):
        r = self._make(bench, [1.0, 2.0, 3.0, 4.0])
        assert r.p50() == pytest.approx(bench.percentile([1.0, 2.0, 3.0, 4.0], 50))

    def test_p99_high_latency(self, bench):
        # 10 values at 10 ms, 90 values at 1000 ms → p99 should be close to 1000
        data = [10.0] * 10 + [1000.0] * 90
        r = self._make(bench, data)
        # p99 index = 0.99 * 99 = 98.01; lower=98, upper=99 (both 1000ms)
        assert r.p99() > 900.0  # outlier values dominate p99

    def test_to_dict_keys(self, bench):
        r = self._make(bench, [5.0, 10.0, 15.0], errors=2)
        d = r.to_dict()
        for key in ("count", "mean_ms", "p50_ms", "p90_ms", "p95_ms", "p99_ms", "error_count"):
            assert key in d, f"Missing key: {key}"
        assert d["count"] == 3
        assert d["error_count"] == 2

    def test_to_dict_values_rounded(self, bench):
        r = self._make(bench, [1.0 / 3.0])  # ~0.333...
        d = r.to_dict()
        # Values should be rounded to 3 decimal places
        assert d["mean_ms"] == round(1.0 / 3.0, 3)

    def test_error_count_tracked(self, bench):
        r = self._make(bench, [1.0], errors=5)
        assert r.error_count == 5


# ---------------------------------------------------------------------------
# _build_parser() / CLI argument parsing
# ---------------------------------------------------------------------------


class TestArgParser:
    def test_defaults(self, bench):
        args = bench._build_parser().parse_args([])
        assert args.url == bench.DEFAULT_URL
        assert args.concurrency == bench.DEFAULT_CONCURRENCY
        assert args.duration == bench.DEFAULT_DURATION_S
        assert args.warmup == bench.DEFAULT_WARMUP_S
        assert args.output_json is False

    def test_custom_url(self, bench):
        args = bench._build_parser().parse_args(["--url", "http://10.0.0.1:9000"])
        assert args.url == "http://10.0.0.1:9000"

    def test_short_flags(self, bench):
        args = bench._build_parser().parse_args(["-c", "20", "-d", "60", "-w", "10"])
        assert args.concurrency == 20
        assert args.duration == 60.0
        assert args.warmup == 10.0

    def test_json_flag(self, bench):
        args = bench._build_parser().parse_args(["--json"])
        assert args.output_json is True

    def test_missing_required_defaults(self, bench):
        # All arguments have defaults; no required args.
        args = bench._build_parser().parse_args([])
        assert args is not None


# ---------------------------------------------------------------------------
# ROUTES constant
# ---------------------------------------------------------------------------


class TestRoutes:
    def test_routes_is_list_of_tuples(self, bench):
        assert isinstance(bench.ROUTES, list)
        for item in bench.ROUTES:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_favicon_is_first_route(self, bench):
        # Favicon must be first so it acts as the HTTP-only baseline
        first_name, first_path = bench.ROUTES[0]
        assert "favicon" in first_name.lower()
        assert first_path == "/favicon.ico"

    def test_all_paths_start_with_slash(self, bench):
        for _, path in bench.ROUTES:
            assert path.startswith("/"), f"Path missing leading slash: {path}"
