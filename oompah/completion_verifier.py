"""Completion verifier — reject bead-close when the agent diff does not
satisfy the acceptance criteria.

Motivating evidence (see issue oompah-zlz_2-y0ns):

* **trickle-icl** (2026-05-07): Agent for a CI fix on PR #23's branch
  ``trickle-rl5`` opened a new branch + new PR instead. Closed the
  bead. Operator had to refile.
* **oompah-zlz_2-jg4** (2026-05-08): Watchdog feature bead specified
  four detectors (D1/D2/D3/D4). Agent shipped only D2 and closed
  the bead.
* **oompah-zlz_2-keb** (2026-05-10): Spec required
  ``ModelProvider.mode`` + UI Mode toggle. Agent shipped only CSS
  badges and closed the bead.

Pattern: bead has clear acceptance criteria → agent ships partial
work → agent self-reports "done" → bead closes → operator later
discovers gap.

Design
------

A two-stage verification pass runs after the worker exits and we
detect that the agent moved the bead to ``closed``. Both stages
fail-open so verification can never become a stuck-loop hazard:

* **Stage 1** (cheap, deterministic): regex-extract file paths and
  Python symbols from the bead's acceptance-criteria section, then
  check the diff contains a touch for each.
* **Stage 2** (LLM-based, only when Stage 1 finds gaps): send the
  acceptance criteria + a diff summary to a small/fast model and
  ask YES/NO whether the diff fulfills the criteria.

If Stage 1 passes → verification passes (no LLM call).
If Stage 1 fails AND Stage 2 says NO → verification rejects.
If Stage 1 fails AND Stage 2 says YES (or errors/times out) →
verification passes.

The verifier is a pure-function module: it inspects state passed in
by the orchestrator and returns a ``VerifierResult`` saying
``passed`` or ``rejected`` along with diagnostic context. The
orchestrator owns the side effects (reopen, comment, escalate).
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

from oompah.models import Issue
from oompah.statuses import NEEDS_CI_FIX, NEEDS_REBASE, canonicalize_status

logger = logging.getLogger(__name__)

# Header patterns that delimit the acceptance-criteria section. Match
# any markdown heading level (``#``/``##``/``###``) for "acceptance
# criteria" (case-insensitive). The section ends at the next markdown
# heading.
_AC_HEADER_RE = re.compile(
    r"^#{1,6}\s*acceptance\s+criteria\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_ANY_HEADER_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)

# Inline-code-quoted tokens — we then classify each match as a file
# path or a Python symbol via :func:`_classify_token`.
_CODE_TOKEN_RE = re.compile(r"`([A-Za-z0-9_./*-][A-Za-z0-9_./*-]*)`")

# Known file extensions used to recognize files when the token has
# no directory separator (e.g. ``plan.md``).
_FILE_EXTENSIONS = frozenset({
    "py", "md", "txt", "json", "yaml", "yml", "toml", "html", "css",
    "js", "ts", "tsx", "jsx", "rs", "go", "sh", "ini", "cfg", "lock",
    "rst", "log", "csv", "tsv", "xml", "sql", "proto", "c", "h", "cc",
    "cpp", "hpp", "rb", "java", "kt", "swift", "dart", "ex", "exs",
})


def _classify_token(token: str) -> str:
    """Return ``"file"``, ``"symbol"``, or ``""`` (ignore).

    A token is a file iff:
    * it contains a ``/`` (path separator), OR
    * it ends in one of the known file extensions in
      :data:`_FILE_EXTENSIONS`.

    A token is a symbol iff:
    * it is NOT a file, AND
    * it looks like a Python identifier or dotted Python identifier
      (``[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)*``), AND
    * it contains either an underscore (``_yolo_retry_ci``) or a
      dot (``ModelProvider.mode``) — keeps us from matching plain
      English words quoted in backticks (``mode``, ``Item``, ...).
    """
    if "://" in token:
        return ""
    # File classification first — covers the dotted-path case where a
    # token has BOTH a dot and an extension.
    if "/" in token:
        return "file"
    head, _, ext = token.rpartition(".")
    if head and ext.lower() in _FILE_EXTENSIONS:
        return "file"
    # Symbol classification.
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", token):
        return ""
    if "." in token or "_" in token:
        return "symbol"
    return ""

# Cap diff size for stage-2 prompt to keep tokens bounded.
_MAX_DIFF_LINES_PER_FILE = 200
_MAX_DIFF_FILES = 30
_LLM_TIMEOUT_S = 20.0

# Labels that bypass verification (their own focus-rails enforce
# correctness).
_BYPASS_LABELS = {"ci-fix", "merge-conflict"}

# Path prefixes that are forbidden in GitHub-backed task diffs.
# Agents running against a GitHub-backed project must not create
# Backlog.md task files — those operations must go through the
# oompah task command wrapper instead.
_BACKLOG_GUARD_PREFIXES: tuple[str, ...] = (
    "backlog/tasks/",
    "backlog/completed/",
)


@dataclass
class ExtractedReferences:
    """Files and symbols pulled from the AC section."""

    files: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    raw_section: str = ""


@dataclass
class Stage1Result:
    """Outcome of the deterministic file/symbol check."""

    references: ExtractedReferences
    diff_files: list[str] = field(default_factory=list)
    diff_content: str = ""
    missing_files: list[str] = field(default_factory=list)
    missing_symbols: list[str] = field(default_factory=list)

    @property
    def has_gaps(self) -> bool:
        return bool(self.missing_files or self.missing_symbols)


@dataclass
class Stage2Result:
    """Outcome of the LLM semantic check."""

    called: bool = False
    verdict: str | None = None  # "yes" | "no" | None
    reasoning: str = ""
    error: str = ""

    @property
    def says_no(self) -> bool:
        return self.verdict == "no"

    @property
    def is_fail_open(self) -> bool:
        """True when we should allow the close — error/timeout/YES."""
        if not self.called:
            return False
        return self.verdict != "no"


@dataclass
class VerifierResult:
    """Final verdict + diagnostics for the orchestrator."""

    passed: bool
    skipped: bool = False
    skip_reason: str = ""
    stage1: Stage1Result | None = None
    stage2: Stage2Result | None = None
    # Newly-added Backlog task/completed files detected in a
    # GitHub-backed task's diff. Non-empty iff the backlog-file
    # guard fired (see :func:`detect_new_backlog_files`).
    new_backlog_files: list[str] = field(default_factory=list)

    def render_rejection_comment(self) -> str:
        """Build the synthetic comment posted to the reopened bead."""
        parts = ["**Completion verifier rejected close.**", ""]
        if self.new_backlog_files:
            parts.append(
                "This task is GitHub-backed. New Backlog.md task files must "
                "not be created — use `oompah task create` (or child-create) "
                "instead. The following file(s) were added:"
            )
            for f in self.new_backlog_files:
                parts.append(f"- `{f}`")
            parts.append("")
            parts.append(
                "Remove the new Backlog file(s) and re-route any follow-up "
                "tasks through the oompah task command wrapper."
            )
            parts.append("")
        if self.stage1 and self.stage1.missing_files:
            parts.append("Files mentioned in acceptance criteria but missing from diff:")
            for f in self.stage1.missing_files:
                parts.append(f"- `{f}`")
            parts.append("")
        if self.stage1 and self.stage1.missing_symbols:
            parts.append("Symbols mentioned in acceptance criteria but missing from diff:")
            for s in self.stage1.missing_symbols:
                parts.append(f"- `{s}`")
            parts.append("")
        if self.stage2 and self.stage2.called and self.stage2.reasoning:
            parts.append(f"LLM reasoning: '{self.stage2.reasoning}'")
        return "\n".join(parts).strip()


def extract_acceptance_section(description: str | None) -> str:
    """Return the body of the ``# Acceptance criteria`` markdown section.

    Returns ``""`` when no such section exists. Stops at the next
    same-or-higher level heading. Case-insensitive on the header.
    """
    if not description:
        return ""
    m = _AC_HEADER_RE.search(description)
    if not m:
        return ""
    start = m.end()
    rest = description[start:]
    # Find the next markdown heading after the AC header. The
    # AC_HEADER match was anchored to a heading line; the next
    # heading ends the section.
    m2 = _ANY_HEADER_RE.search(rest)
    if m2:
        return rest[: m2.start()].strip()
    return rest.strip()


def extract_references(section: str) -> ExtractedReferences:
    """Pull file paths and python symbols out of an AC section.

    Only inline-code-quoted tokens are extracted. Plain prose like
    "the providers page" is ignored — we want declarative
    references, not prose mentions.
    """
    refs = ExtractedReferences(raw_section=section)
    if not section:
        return refs

    seen_files: set[str] = set()
    seen_syms: set[str] = set()

    for m in _CODE_TOKEN_RE.finditer(section):
        token = m.group(1)
        kind = _classify_token(token)
        if kind == "file" and token not in seen_files:
            seen_files.add(token)
            refs.files.append(token)
        elif kind == "symbol" and token not in seen_syms:
            seen_syms.add(token)
            refs.symbols.append(token)

    return refs


def compute_diff(workspace_path: str, base_branch: str) -> tuple[list[str], str]:
    """Run ``git diff`` against ``base_branch`` to find changed files +
    diff body.

    Returns ``(files, diff_body)``. ``files`` is the list of changed
    file paths (output of ``git diff --name-only``). ``diff_body`` is
    a capped textual diff suitable for LLM consumption. On any
    subprocess failure returns ``([], "")``.
    """
    git = shutil.which("git")
    if not git:
        logger.warning("git not on PATH; completion verifier cannot diff")
        return [], ""

    # Try a few possible base refs in order. ``origin/<branch>`` is
    # the canonical comparison; ``<branch>`` works when the worktree
    # has a local copy.
    bases = []
    if base_branch:
        bases.extend([f"origin/{base_branch}", base_branch])
    bases.append("HEAD~1")  # last-resort fallback

    files: list[str] = []
    diff_body = ""
    used_base = ""
    for base in bases:
        try:
            r = subprocess.run(
                [git, "diff", "--name-only", f"{base}...HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("git diff --name-only failed against %s: %s", base, exc)
            continue
        if r.returncode != 0:
            continue
        used_base = base
        files = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
        break

    if not used_base:
        return [], ""

    try:
        r2 = subprocess.run(
            [git, "diff", "--stat", f"{used_base}...HEAD"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=15,
        )
        stat = r2.stdout if r2.returncode == 0 else ""
    except (subprocess.TimeoutExpired, OSError):
        stat = ""

    # Pull a capped per-file diff for stage 2 prompting.
    pieces: list[str] = [stat]
    for f in files[:_MAX_DIFF_FILES]:
        try:
            r3 = subprocess.run(
                [git, "diff", f"{used_base}...HEAD", "--", f],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, OSError):
            continue
        if r3.returncode != 0:
            continue
        lines = r3.stdout.splitlines()
        if len(lines) > _MAX_DIFF_LINES_PER_FILE:
            lines = lines[:_MAX_DIFF_LINES_PER_FILE] + [
                f"... (truncated, {len(lines) - _MAX_DIFF_LINES_PER_FILE} more lines)",
            ]
        pieces.append("\n".join(lines))
    diff_body = "\n".join(pieces).strip()

    return files, diff_body


def compute_added_files(workspace_path: str, base_branch: str) -> list[str]:
    """Return only newly-added (not modified or deleted) files in the diff.

    Uses ``--diff-filter=A`` so we only flag files the agent actually
    *created*. Returns ``[]`` on any subprocess failure (fail-open).
    """
    git = shutil.which("git")
    if not git:
        logger.warning("git not on PATH; cannot check for new backlog files")
        return []

    bases = []
    if base_branch:
        bases.extend([f"origin/{base_branch}", base_branch])
    bases.append("HEAD~1")

    for base in bases:
        try:
            r = subprocess.run(
                [git, "diff", "--name-only", "--diff-filter=A", f"{base}...HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning(
                "git diff --diff-filter=A failed against %s: %s", base, exc
            )
            continue
        if r.returncode != 0:
            continue
        return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    return []


def detect_new_backlog_files(added_files: list[str]) -> list[str]:
    """Return paths from *added_files* that are new Backlog task/completed files.

    Matches any file whose repo-relative path starts with
    ``backlog/tasks/`` or ``backlog/completed/``.  Only newly-added
    files should be passed in (see :func:`compute_added_files`).
    """
    return [
        f for f in added_files
        if any(f.startswith(prefix) for prefix in _BACKLOG_GUARD_PREFIXES)
    ]


def _file_present(target: str, diff_files: list[str]) -> bool:
    """Return True iff ``target`` is a hit against the diff file list.

    Exact match wins. A glob pattern in ``target`` (``tests/test_*.py``)
    is matched as a directory prefix plus filename glob.
    """
    if target in diff_files:
        return True
    if "*" in target:
        # Convert simple globs to a regex. Anchor at start.
        regex_src = re.escape(target).replace(r"\*", "[^/]*")
        regex = re.compile("^" + regex_src + "$")
        return any(regex.match(f) for f in diff_files)
    # Allow trailing-segment matches in either direction:
    #  * AC says ``foo/bar/baz.py``, diff is ``bar/baz.py`` (worktree
    #    rooted at a sub-package), OR
    #  * AC says ``oompah/foo.py``, diff is ``foo.py``.
    for f in diff_files:
        if f.endswith("/" + target) or target.endswith("/" + f):
            return True
        # Same basename — last-resort heuristic. Treat
        # ``oompah/foo.py`` and ``foo.py`` as a match.
        if "/" in target and target.rsplit("/", 1)[-1] == f:
            return True
        if "/" in f and f.rsplit("/", 1)[-1] == target:
            return True
    return False


def _symbol_present(symbol: str, diff_content: str) -> bool:
    """Return True iff ``symbol`` shows up in the diff content.

    A *meaningful* hit needs an added (``+``-prefixed) line in the
    diff that contains the symbol — not just a context line that
    happened to mention it. We accept ``def <symbol>``, ``class
    <symbol>``, ``<symbol> =`` (attribute / dataclass assignment),
    or any added line containing the symbol token.
    """
    if not diff_content:
        return False
    # Strip the leading-dot half of dotted symbols for line-level
    # matching. ``ModelProvider.mode`` → search for both the full
    # token and the attribute name.
    bare = symbol.rsplit(".", 1)[-1]
    needle_re = re.compile(
        r"^\+(?!\+\+)" r"[^\n]*\b(?:" + re.escape(symbol) + "|" + re.escape(bare) + r")\b",
        re.MULTILINE,
    )
    return bool(needle_re.search(diff_content))


def run_stage1(
    issue: Issue,
    workspace_path: str,
    base_branch: str,
) -> Stage1Result:
    """Run the deterministic file/symbol reference check.

    Extracts references from the issue's acceptance-criteria section
    and checks they appear in the agent's diff. Returns a result
    describing which (if any) references are missing.
    """
    section = extract_acceptance_section(issue.description)
    refs = extract_references(section)
    files, diff_content = compute_diff(workspace_path, base_branch)

    result = Stage1Result(
        references=refs,
        diff_files=files,
        diff_content=diff_content,
    )

    for f in refs.files:
        if not _file_present(f, files):
            result.missing_files.append(f)

    for s in refs.symbols:
        if not _symbol_present(s, diff_content):
            result.missing_symbols.append(s)

    return result


def _build_stage2_prompt(ac_section: str, diff_summary: str) -> str:
    return (
        "You are auditing whether an agent's code diff satisfies a "
        "bead's acceptance criteria.\n\n"
        "Bead acceptance criteria:\n"
        f"```\n{ac_section}\n```\n\n"
        "Agent's diff summary (output of `git diff` against the base "
        "branch, truncated):\n"
        f"```\n{diff_summary}\n```\n\n"
        "Question: Does this diff fulfill the acceptance criteria?\n"
        "Reply with exactly one line in this format:\n"
        "VERDICT: YES — <one-sentence reason>\n"
        "or\n"
        "VERDICT: NO — <one-sentence reason>\n"
    )


def _parse_stage2_response(content: str) -> tuple[str | None, str]:
    """Parse the model's reply.

    Looks for ``VERDICT: YES`` or ``VERDICT: NO`` (case-insensitive).
    Returns ``(verdict, reasoning)`` where verdict is "yes" / "no" /
    None and reasoning is the trailing sentence (or full content if
    not parseable).
    """
    if not content:
        return None, ""
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("VERDICT:"):
            rest = line[len("VERDICT:"):].strip()
            # Strip leading YES/NO from rest.
            r_upper = rest.upper()
            if r_upper.startswith("YES"):
                tail = rest[3:].lstrip(" —-:").strip()
                return "yes", tail or "agent diff matches criteria"
            if r_upper.startswith("NO"):
                tail = rest[2:].lstrip(" —-:").strip()
                return "no", tail or "agent diff does not match criteria"
    # Fallback: scan for bare YES/NO at start of any line.
    head = content.strip().split("\n", 1)[0].strip().upper()
    if head.startswith("YES"):
        return "yes", content.strip().splitlines()[0]
    if head.startswith("NO"):
        return "no", content.strip().splitlines()[0]
    return None, content.strip()[:200]


def run_stage2_sync(
    ac_section: str,
    diff_summary: str,
    provider: Any,
    *,
    timeout_s: float = _LLM_TIMEOUT_S,
) -> Stage2Result:
    """Run the LLM semantic check synchronously.

    Uses the provider's ``fast`` model role when present (falling
    back to ``default_model``). Fail-open on any error.
    """
    result = Stage2Result(called=True)
    if provider is None:
        result.error = "no provider"
        return result
    base_url = (getattr(provider, "base_url", "") or "").rstrip("/")
    if not base_url:
        result.error = "no base_url on provider"
        return result

    model = (getattr(provider, "model_roles", None) or {}).get("fast")
    if not model:
        model = getattr(provider, "default_model", None)
    if not model:
        models = getattr(provider, "models", None) or []
        if models:
            model = models[0]
    if not model:
        result.error = "no model resolved"
        return result

    prompt = _build_stage2_prompt(ac_section, diff_summary)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.0,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {getattr(provider, 'api_key', None) or ''}",
        "User-Agent": "oompah/0.1 completion-verifier",
    }
    url = f"{base_url}/chat/completions"

    try:
        from oompah.api_agent import _build_ssl_context, _http_post  # lazy

        ssl_ctx = _build_ssl_context()
        # _http_post is synchronous and returns parsed JSON. It has
        # an internal HTTP timeout (currently 60s default) that
        # bounds the worst case; we don't get to override it per
        # call, but errors propagate as exceptions which we swallow.
        del timeout_s  # parameter reserved for future async variant
        response = _http_post(url, headers, body, ssl_ctx)
    except Exception as exc:
        result.error = f"http_post failed: {exc}"
        logger.warning("completion verifier stage 2 call failed: %s", exc)
        return result

    try:
        content = response["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        result.error = f"unexpected response shape: {exc}"
        return result

    verdict, reasoning = _parse_stage2_response(content)
    result.verdict = verdict
    result.reasoning = reasoning
    return result


def should_skip_verification(
    issue: Issue,
    *,
    attempt: int = 0,
    escalate_after_attempts: int = 1,
) -> tuple[bool, str]:
    """Return (skip, reason) for the issue-level skip rules.

    Skip when:
    * The issue type is ``epic`` (epics auto-close when children
      close; no per-bead diff exists).
    * The issue has a CI-fix/rebase status or legacy label (their own
      focus-rail enforces correctness).
    * The ``attempt`` count is at or above
      ``escalate_after_attempts`` (we're already escalating; don't
      keep blocking the close).
    * The acceptance-criteria section is empty (nothing to check).
    """
    if (issue.issue_type or "").strip().lower() == "epic":
        return True, "issue is an epic"
    label_set = {(l or "").strip().lower() for l in (issue.labels or [])}
    intersection = label_set & _BYPASS_LABELS
    if intersection:
        return True, f"bypass label present: {','.join(sorted(intersection))}"
    canonical_status = canonicalize_status(issue.state)
    if canonical_status in {NEEDS_CI_FIX, NEEDS_REBASE}:
        return True, f"bypass status present: {canonical_status}"
    if attempt and attempt >= escalate_after_attempts:
        return True, f"attempt {attempt} >= escalate_after_attempts={escalate_after_attempts}"
    section = extract_acceptance_section(issue.description)
    if not section:
        return True, "no acceptance criteria"
    return False, ""


def verify_completion(
    issue: Issue,
    workspace_path: str,
    base_branch: str,
    provider: Any | None,
    *,
    attempt: int = 0,
    escalate_after_attempts: int = 1,
    enable_stage2: bool = True,
) -> VerifierResult:
    """Top-level verification routine.

    Runs the backlog-file guard (for non-Backlog oompah-managed tasks) first, then
    the skip-rules, then Stage 1 (regex check), then Stage 2 (LLM
    check) if Stage 1 found gaps. Fail-open at every boundary.

    Backlog-file guard
    ------------------
    GitHub-backed and native oompah Markdown tasks must not add files under
    ``backlog/tasks/`` or ``backlog/completed/``. If the agent created such
    files the verifier immediately rejects with a clear diagnostic and a
    pointer to ``oompah task create``. The guard fires *before* the standard
    skip rules so that epic/ci-fix labels cannot accidentally bypass the policy
    check.
    """
    # ----------------------------------------------------------------
    # 0. Backlog-file guard (non-Backlog oompah-managed tasks only).
    # ----------------------------------------------------------------
    if (issue.tracker_kind or "").strip().lower() in {"github_issues", "oompah_md"}:
        try:
            added = compute_added_files(workspace_path, base_branch)
            new_backlog = detect_new_backlog_files(added)
            if new_backlog:
                logger.warning(
                    "completion verifier: GitHub-backed task %s added "
                    "Backlog task file(s) — rejecting close: %s",
                    issue.identifier,
                    new_backlog,
                )
                return VerifierResult(passed=False, new_backlog_files=new_backlog)
        except Exception as exc:
            # Fail open — a git error must not permanently block the close.
            logger.warning(
                "completion verifier: backlog-file guard error for %s; "
                "failing open: %s",
                issue.identifier,
                exc,
            )

    # ----------------------------------------------------------------
    # 1. Standard skip rules.
    # ----------------------------------------------------------------
    skip, reason = should_skip_verification(
        issue,
        attempt=attempt,
        escalate_after_attempts=escalate_after_attempts,
    )
    if skip:
        return VerifierResult(passed=True, skipped=True, skip_reason=reason)

    try:
        stage1 = run_stage1(issue, workspace_path, base_branch)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "Completion verifier stage 1 raised; failing open. issue=%s err=%s",
            issue.identifier, exc,
        )
        return VerifierResult(passed=True, skipped=True, skip_reason=f"stage1 error: {exc}")

    if not stage1.has_gaps:
        return VerifierResult(passed=True, stage1=stage1)

    if not enable_stage2:
        # Operator set OOMPAH_VERIFY_COMPLETION_LLM=false — keep
        # Stage 1 as the deterministic gate but be cautious: only
        # reject when files (not just symbols) are missing. Pure
        # symbol-misses are noisier and need the LLM for nuance.
        if stage1.missing_files:
            return VerifierResult(passed=False, stage1=stage1)
        return VerifierResult(passed=True, stage1=stage1)

    try:
        ac_section = stage1.references.raw_section
        diff_summary = stage1.diff_content or "(empty diff)"
        stage2 = run_stage2_sync(ac_section, diff_summary, provider)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "Completion verifier stage 2 raised; failing open. issue=%s err=%s",
            issue.identifier, exc,
        )
        return VerifierResult(passed=True, stage1=stage1, skip_reason=f"stage2 error: {exc}")

    if stage2.is_fail_open:
        return VerifierResult(passed=True, stage1=stage1, stage2=stage2)
    if stage2.says_no:
        return VerifierResult(passed=False, stage1=stage1, stage2=stage2)
    # No verdict parseable — fail open.
    return VerifierResult(passed=True, stage1=stage1, stage2=stage2)
