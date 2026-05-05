"""Tests for scripts/merge-queue-cutover.sh (Step 5 of submit-queue rollout).

The script dispatches to two distinct GitHub APIs depending on the
target repo's ownership (see ``repo_api_kind`` in the script):

- **`ruleset`** (org-owned): full GitHub Merge Queue via
  ``POST /repos/{owner}/{repo}/rulesets`` with a ``merge_queue`` rule
  + ``required_status_checks`` rule.
- **`branch_protection`** (user-owned free-tier): legacy
  ``PUT /repos/{owner}/{repo}/branches/{branch}/protection``.
  Required status checks only — the merge_queue rule type is not
  supported on user-owned repos.

What we test:

1. Bash itself parses the script (``bash -n``).
2. Usage / arg validation rejects bad invocations.
3. ``repo_api_kind`` returns the right backend per repo.
4. ``build_payload`` (trickle) produces well-formed merge_queue JSON.
5. ``build_branch_protection_payload`` (oompah) produces the legacy
   shape with the matrix's check names.
6. ``cmd_apply`` chooses POST/PUT vs ``branches/.../protection`` based
   on the repo's kind.
7. ``cmd_rollback`` calls DELETE on the correct endpoint.

We avoid all real network calls by stubbing ``gh`` on PATH and
recording its argv + stdin to a log file the test can inspect.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "merge-queue-cutover.sh"


# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------


def test_script_exists_and_is_executable() -> None:
    assert SCRIPT.exists(), f"missing {SCRIPT}"
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, f"{SCRIPT} not executable"


def test_script_has_valid_bash_syntax() -> None:
    """`bash -n` parses the script without complaint."""
    res = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"bash -n failed: {res.stderr}"


# ---------------------------------------------------------------------------
# Usage / arg validation
# ---------------------------------------------------------------------------


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Invoke the script with PATH munged to use a fake `gh` if requested."""
    env = os.environ.copy()
    fake_path = kwargs.pop("fake_gh_dir", None)
    if fake_path is not None:
        env["PATH"] = f"{fake_path}{os.pathsep}{env.get('PATH', '')}"
    return subprocess.run(
        [str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        **kwargs,
    )


def test_no_args_prints_usage_and_exits_nonzero() -> None:
    res = _run([])
    assert res.returncode != 0
    assert "Usage:" in res.stderr


def test_help_flag_prints_usage() -> None:
    res = _run(["apply", "--help"])
    assert res.returncode != 0
    assert "Usage:" in res.stderr


def test_apply_without_repo_exits_nonzero() -> None:
    res = _run(["apply"])
    assert res.returncode != 0
    assert "--repo required" in res.stderr or "Usage:" in res.stderr


def test_unknown_subcommand_exits_nonzero() -> None:
    res = _run(["frobnicate", "--repo", "lesserevil/oompah"])
    assert res.returncode != 0


# ---------------------------------------------------------------------------
# repo_api_kind dispatch
# ---------------------------------------------------------------------------


def _source_and_eval(snippet: str) -> subprocess.CompletedProcess:
    """Source the script in a fresh subshell and run an arbitrary
    function call. Used to test internal helpers without going through
    the network."""
    full = textwrap.dedent(
        f"""
        set -euo pipefail
        # shellcheck disable=SC1090
        source "{SCRIPT}"
        {snippet}
        """
    )
    return subprocess.run(
        ["bash", "-c", full],
        capture_output=True,
        text=True,
    )


def test_repo_api_kind_oompah_is_branch_protection() -> None:
    res = _source_and_eval('repo_api_kind "lesserevil/oompah"')
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "branch_protection"


def test_repo_api_kind_trickle_is_ruleset() -> None:
    res = _source_and_eval('repo_api_kind "NVIDIA-Omniverse/trickle"')
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "ruleset"


def test_repo_api_kind_unknown_repo_fails() -> None:
    res = _source_and_eval('repo_api_kind "some/unrelated-repo"')
    assert res.returncode != 0
    assert "no submit-queue mapping" in res.stderr


# ---------------------------------------------------------------------------
# Payload shape — ruleset (trickle)
# ---------------------------------------------------------------------------


def _extract_ruleset_payload(repo: str) -> dict:
    snippet = f'build_payload "{repo}"'
    res = _source_and_eval(snippet)
    assert res.returncode == 0, f"build_payload failed: {res.stderr}"
    return json.loads(res.stdout)


def test_trickle_ruleset_payload_shape() -> None:
    payload = _extract_ruleset_payload("NVIDIA-Omniverse/trickle")

    assert payload["name"] == "submit-queue-main"
    assert payload["target"] == "branch"
    assert payload["enforcement"] == "active"
    assert payload["conditions"]["ref_name"]["include"] == ["refs/heads/main"]

    rules_by_type = {r["type"]: r for r in payload["rules"]}
    assert "merge_queue" in rules_by_type
    assert "required_status_checks" in rules_by_type

    mq = rules_by_type["merge_queue"]["parameters"]
    # Per docs/submit-queue.md §Step 5: trickle CI is slow (~60min).
    # batch_size=1 (NO BATCHING — protects against shared-batch flake);
    # build_concurrency=2-3 (we picked 3 for parallel throughput).
    assert mq["merge_method"] == "SQUASH"
    assert mq["max_entries_to_build"] == 3
    assert mq["max_entries_to_merge"] == 1, (
        "trickle MUST NOT batch — a shared batch ejection costs ~60min of CI"
    )
    assert mq["min_entries_to_merge"] == 1
    assert mq["check_response_timeout_minutes"] == 60
    assert mq["grouping_strategy"] == "ALLGREEN"

    contexts = sorted(
        c["context"]
        for c in rules_by_type["required_status_checks"]["parameters"][
            "required_status_checks"
        ]
    )
    # All ci.yml + e2e.yml jobs that run on `merge_group:`. Tier-C is
    # schedule-only and is correctly excluded.
    assert contexts == sorted(
        [
            "lint",
            "test-linux",
            "smoke-deb",
            "test-macos",
            "test-windows",
            "tier-a-unit",
            "build-matrix",
            "tier-b-linux",
            "tier-b-windows",
            "tier-b-macos",
        ]
    )


def test_unknown_repo_ruleset_payload_fails() -> None:
    """build_payload refuses repos it doesn't have a tuning for."""
    res = _source_and_eval('build_payload "some/unrelated-repo"')
    assert res.returncode != 0
    assert "no merge-queue payload" in res.stderr


# ---------------------------------------------------------------------------
# Payload shape — branch_protection (oompah)
# ---------------------------------------------------------------------------


def _extract_branch_protection_payload(repo: str) -> dict:
    snippet = f'build_branch_protection_payload "{repo}"'
    res = _source_and_eval(snippet)
    assert res.returncode == 0, (
        f"build_branch_protection_payload failed: {res.stderr}"
    )
    return json.loads(res.stdout)


def test_oompah_branch_protection_payload_shape() -> None:
    payload = _extract_branch_protection_payload("lesserevil/oompah")

    # Legacy branch-protection PUT body — not the rulesets shape.
    rsc = payload["required_status_checks"]
    contexts = sorted(c["context"] for c in rsc["checks"])
    assert contexts == ["test (3.11)", "test (3.12)", "test (3.13)"]
    # `strict` (require branch up-to-date) is False — we don't want to
    # force a rebase on every PR; the YOLO orchestrator handles that.
    assert rsc["strict"] is False
    # Required-PR-reviews is null because we don't gate on review count;
    # YOLO is the merge mechanism.
    assert payload["required_pull_request_reviews"] is None
    # Conservative defaults — not enforced for admins, no force-pushes.
    assert payload["enforce_admins"] is False
    assert payload["allow_force_pushes"] is False
    assert payload["allow_deletions"] is False
    assert payload["lock_branch"] is False


def test_unknown_repo_branch_protection_payload_fails() -> None:
    res = _source_and_eval(
        'build_branch_protection_payload "some/unrelated-repo"'
    )
    assert res.returncode != 0
    assert "no branch-protection payload" in res.stderr


# ---------------------------------------------------------------------------
# apply / rollback / status flow with stubbed gh
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_gh_dir(tmp_path: Path) -> Path:
    """Create a stub `gh` on PATH that records argv + stdin to a log
    file, and returns canned responses. The stub never touches the
    network.

    Tests can prime two response files:
      - ``list_out.txt`` — what the LIST rulesets endpoint returns
        (plain id per line, or empty for "no existing ruleset").
      - ``protection_exists.txt`` — non-empty means the legacy
        branch-protection probe returns 0; empty means it returns 1.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "gh.log"
    list_out = tmp_path / "list_out.txt"
    list_out.write_text("")  # default: no existing ruleset
    protection_exists = tmp_path / "protection_exists.txt"
    protection_exists.write_text("")  # default: no protection

    stub = bin_dir / "gh"
    stub.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            # Fake gh stub. Logs argv + stdin.
            {{
                echo "ARGV: $*"
                if [ ! -t 0 ]; then
                    echo "STDIN_BEGIN"
                    cat
                    echo
                    echo "STDIN_END"
                fi
                echo "---"
            }} >> "{log}"

# Distinguish READ (no -X flag) from WRITE (-X POST/PUT/DELETE).
            # Writes always succeed; reads consult the canned-response files.
            is_write=0
            prev=""
            for arg in "$@"; do
                if [ "$prev" = "-X" ]; then
                    case "$arg" in
                        POST|PUT|DELETE|PATCH) is_write=1 ;;
                    esac
                fi
                prev="$arg"
            done

            if [ "$is_write" = "1" ]; then
                # Pretend the write succeeded.
                echo '{{}}'
                exit 0
            fi

            # Read paths.
            # `gh api repos/<repo>/rulesets ...` — list path. Emits
            # whatever was put in list_out.txt.
            for arg in "$@"; do
                case "$arg" in
                    repos/*/rulesets)
                        cat "{list_out}"
                        exit 0
                        ;;
                esac
            done

            # `gh api repos/<repo>/branches/main/protection` (probe).
            # Return 0 iff protection_exists.txt is non-empty.
            for arg in "$@"; do
                case "$arg" in
                    repos/*/branches/*/protection|repos/*/branches/*/protection/required_status_checks)
                        if [ -s "{protection_exists}" ]; then
                            echo '{{"required_status_checks":{{"contexts":["test (3.11)"]}}}}'
                            exit 0
                        else
                            exit 1
                        fi
                        ;;
                esac
            done

            # `gh api repos/<repo>/rules/branches/main` — used by status.
            for arg in "$@"; do
                case "$arg" in
                    repos/*/rules/branches/main)
                        echo '[]'
                        exit 0
                        ;;
                esac
            done

            # Default: emit a benign object.
            echo '{{}}'
            """
        )
    )
    stub.chmod(0o755)
    return bin_dir


def _read_log(fake_gh_dir: Path) -> list[str]:
    log = fake_gh_dir.parent / "gh.log"
    if not log.exists():
        return []
    return [
        block.strip()
        for block in log.read_text().split("---")
        if block.strip()
    ]


# --- ruleset (trickle) flow -------------------------------------------------


def test_apply_trickle_creates_when_no_existing_ruleset(
    fake_gh_dir: Path,
) -> None:
    list_out = fake_gh_dir.parent / "list_out.txt"
    list_out.write_text("")  # no id → CREATE path
    res = _run(
        ["apply", "--repo", "NVIDIA-Omniverse/trickle"],
        fake_gh_dir=fake_gh_dir,
    )
    assert res.returncode == 0, f"apply failed: {res.stderr}"
    assert "Creating new ruleset" in res.stdout

    blocks = _read_log(fake_gh_dir)
    assert any("ARGV:" in b and "/rulesets" in b for b in blocks)
    post_blocks = [b for b in blocks if "ARGV:" in b and "-X POST" in b]
    assert post_blocks, "expected a POST to create the ruleset"
    full_log = "\n".join(blocks)
    # Confirm trickle's payload (not oompah's) was sent.
    assert '"name": "submit-queue-main"' in full_log
    assert "tier-b-linux" in full_log


def test_apply_trickle_updates_when_existing_ruleset(
    fake_gh_dir: Path,
) -> None:
    list_out = fake_gh_dir.parent / "list_out.txt"
    list_out.write_text("9999\n")  # existing id → UPDATE path
    res = _run(
        ["apply", "--repo", "NVIDIA-Omniverse/trickle"],
        fake_gh_dir=fake_gh_dir,
    )
    assert res.returncode == 0, f"apply failed: {res.stderr}"
    assert "Updating existing ruleset id=9999" in res.stdout

    blocks = _read_log(fake_gh_dir)
    put_blocks = [
        b
        for b in blocks
        if "ARGV:" in b and "-X PUT" in b and "rulesets/9999" in b
    ]
    assert put_blocks, "expected a PUT to /rulesets/9999"


def test_rollback_trickle_no_existing_is_noop(fake_gh_dir: Path) -> None:
    list_out = fake_gh_dir.parent / "list_out.txt"
    list_out.write_text("")
    res = _run(
        ["rollback", "--repo", "NVIDIA-Omniverse/trickle"],
        fake_gh_dir=fake_gh_dir,
    )
    assert res.returncode == 0
    assert "Nothing to do" in res.stderr or "No '" in res.stderr


def test_rollback_trickle_deletes_when_present(fake_gh_dir: Path) -> None:
    list_out = fake_gh_dir.parent / "list_out.txt"
    list_out.write_text("12345\n")
    res = _run(
        ["rollback", "--repo", "NVIDIA-Omniverse/trickle"],
        fake_gh_dir=fake_gh_dir,
    )
    assert res.returncode == 0
    blocks = _read_log(fake_gh_dir)
    del_blocks = [
        b
        for b in blocks
        if "ARGV:" in b and "-X DELETE" in b and "rulesets/12345" in b
    ]
    assert del_blocks, "expected a DELETE to /rulesets/12345"


# --- branch_protection (oompah) flow ----------------------------------------


def test_apply_oompah_uses_branch_protection_put(fake_gh_dir: Path) -> None:
    """oompah's `apply` must hit the legacy branches/main/protection PUT,
    not the rulesets endpoint — merge_queue rule type is unsupported on
    user-owned repos."""
    res = _run(
        ["apply", "--repo", "lesserevil/oompah"],
        fake_gh_dir=fake_gh_dir,
    )
    assert res.returncode == 0, f"apply failed: {res.stderr}"
    assert "branch protection" in res.stdout.lower()

    blocks = _read_log(fake_gh_dir)
    put_blocks = [
        b
        for b in blocks
        if "ARGV:" in b
        and "-X PUT" in b
        and "branches/main/protection" in b
    ]
    assert put_blocks, (
        "expected a PUT to /branches/main/protection; got:\n"
        + "\n".join(blocks)
    )

    # Should NOT have hit the rulesets endpoint.
    ruleset_blocks = [
        b for b in blocks if "rulesets" in b and "ARGV:" in b
    ]
    assert not ruleset_blocks, (
        "oompah apply must not touch /rulesets endpoint: "
        + "\n".join(ruleset_blocks)
    )

    # Confirm the payload included the matrix check names.
    full_log = "\n".join(blocks)
    assert "test (3.11)" in full_log
    assert "test (3.12)" in full_log
    assert "test (3.13)" in full_log


def test_rollback_oompah_no_protection_is_noop(fake_gh_dir: Path) -> None:
    """When no branch protection exists, rollback exits cleanly."""
    protection_exists = fake_gh_dir.parent / "protection_exists.txt"
    protection_exists.write_text("")  # no protection
    res = _run(
        ["rollback", "--repo", "lesserevil/oompah"],
        fake_gh_dir=fake_gh_dir,
    )
    assert res.returncode == 0
    assert (
        "Nothing to do" in res.stderr
        or "No branch protection" in res.stderr
    )


def test_rollback_oompah_deletes_branch_protection(
    fake_gh_dir: Path,
) -> None:
    """When branch protection IS present, rollback hits DELETE on the
    legacy endpoint (not /rulesets)."""
    protection_exists = fake_gh_dir.parent / "protection_exists.txt"
    protection_exists.write_text("yes")  # protection present
    res = _run(
        ["rollback", "--repo", "lesserevil/oompah"],
        fake_gh_dir=fake_gh_dir,
    )
    assert res.returncode == 0

    blocks = _read_log(fake_gh_dir)
    del_blocks = [
        b
        for b in blocks
        if "ARGV:" in b
        and "-X DELETE" in b
        and "branches/main/protection" in b
    ]
    assert del_blocks, (
        "expected DELETE on /branches/main/protection; got:\n"
        + "\n".join(blocks)
    )
