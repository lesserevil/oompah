"""Auto-repair and quarantine logic for git-conflicted Backlog.md task files.

When oompah's managed repo checkout has unresolved git conflicts in backlog
task files (e.g. from autostash+pull collisions), this module:

1. Detects conflict markers (``<<<<<<<``) in backlog task files.
2. Attempts a deterministic structured repair that preserves canonical
   lifecycle fields from both sides: status, comments, final_summary,
   oompah.task_costs, dependencies, labels, parent_task_id, updated_date.
3. Validates the repaired file through the YAML parser used by BacklogMdTracker.
4. Returns a result indicating whether repair succeeded.

Callers in ``projects.sync_project_sources()`` use this to either repair
in-place or quarantine (pause) the affected project.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Regex to detect git conflict markers (any of the three kinds)
_CONFLICT_OPEN = re.compile(r"^<{7} ", re.MULTILINE)
# Conflict block: opening marker, ours content, separator, theirs content, closing
_CONFLICT_BLOCK_RE = re.compile(
    r"^<{7}[^\n]*\n(.*?)\n={7}\n(.*?)\n>{7}[^\n]*$",
    re.DOTALL | re.MULTILINE,
)

# Fields that oompah manages and that we want to preserve from the
# more-advanced side (status + newest date side wins).
_LIFECYCLE_STATUS_ORDER = [
    "archived",
    "merged",
    "done",
    "in review",
    "needs rebase",
    "needs ci fix",
    "decomposed",
    "duplicate candidate",
    "in progress",
    "needs human",
    "needs answer",
    "open",
    "backlog",
    "to do",
    "",
]

# Canonical fields where we take the union of both sides (lists).
_UNION_FIELDS = frozenset({"dependencies", "labels"})
# Fields where we take whichever side is non-empty.
_PREFER_NONEMPTY_FIELDS = frozenset({
    "parent",
    "parent_task_id",
    "final_summary",
    "finalsummary",
    "oompah.task_costs",
})


def has_conflict_markers(content: str) -> bool:
    """Return True if *content* contains git conflict markers."""
    return bool(_CONFLICT_OPEN.search(content))


def _status_priority(status: str | None) -> int:
    """Return a sort key where 0 = most-advanced lifecycle status.

    Lower number = more advanced (Done > In Review > In Progress > ...).
    """
    key = str(status or "").strip().lower()
    try:
        return _LIFECYCLE_STATUS_ORDER.index(key)
    except ValueError:
        # Unknown status — treat as intermediate
        return len(_LIFECYCLE_STATUS_ORDER) // 2


def _parse_date(value: Any) -> float | None:
    """Parse an ISO-8601 date/datetime string and return a float timestamp.

    Returns None when the value cannot be parsed.
    """
    from datetime import datetime, timezone

    if not value:
        return None
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        s = str(value)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _pick_newer_date(a: Any, b: Any) -> Any:
    """Return the value representing the newer date, or *a* when tied/unparseable."""
    ta = _parse_date(a)
    tb = _parse_date(b)
    if ta is None and tb is None:
        return a
    if ta is None:
        return b
    if tb is None:
        return a
    return a if ta >= tb else b


def _merge_string_list(a: Any, b: Any) -> list[str]:
    """Return the union of two list-or-comma-string values."""
    def to_list(v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return []

    seen: dict[str, None] = {}  # ordered set
    for item in to_list(a) + to_list(b):
        seen[item] = None
    return list(seen.keys())


def _merge_oompah_costs(a: Any, b: Any) -> Any:
    """Merge oompah.task_costs — prefer the side with more data."""
    if not a:
        return b
    if not b:
        return a
    # If both are dicts, merge: take the max of numeric values
    if isinstance(a, dict) and isinstance(b, dict):
        merged = dict(a)
        for k, v in b.items():
            if k not in merged:
                merged[k] = v
            else:
                try:
                    merged[k] = max(float(merged[k]), float(v))
                except (TypeError, ValueError):
                    pass  # keep a's value
        return merged
    # Fall back to whichever is non-empty
    return a


def _merge_frontmatter(meta_a: dict, meta_b: dict) -> dict:
    """Merge two parsed frontmatter dicts using structured rules.

    Rules:
    - ``status``: take the more-advanced lifecycle status.
    - ``updated_date``: take the newer value.
    - ``final_summary``: take the non-empty value (prefer newer-date side).
    - ``oompah.task_costs``: merge dicts, preferring max numeric values.
    - ``dependencies``, ``labels``: union of both sides.
    - ``parent``, ``parent_task_id``: take the non-empty value.
    - All other keys: take from side with newer ``updated_date``.
    """
    # Determine which side is "newer" overall based on updated_date
    date_a = _parse_date(meta_a.get("updated_date"))
    date_b = _parse_date(meta_b.get("updated_date"))
    if date_a is None and date_b is None:
        newer_meta, older_meta = meta_a, meta_b
    elif date_b is None or (date_a is not None and date_a >= date_b):
        newer_meta, older_meta = meta_a, meta_b
    else:
        newer_meta, older_meta = meta_b, meta_a

    result: dict = dict(newer_meta)
    # Merge in missing keys from the older side
    for key, value in older_meta.items():
        if key not in result:
            result[key] = value

    # status: take the more-advanced one
    status_a = meta_a.get("status")
    status_b = meta_b.get("status")
    if status_a is not None and status_b is not None:
        if _status_priority(status_a) <= _status_priority(status_b):
            result["status"] = status_a
        else:
            result["status"] = status_b
    elif status_a is not None:
        result["status"] = status_a
    elif status_b is not None:
        result["status"] = status_b

    # updated_date: take the newer value
    result["updated_date"] = _pick_newer_date(
        meta_a.get("updated_date"), meta_b.get("updated_date")
    )

    # union fields
    for field in _UNION_FIELDS:
        a_val = meta_a.get(field)
        b_val = meta_b.get(field)
        if a_val is not None or b_val is not None:
            merged_list = _merge_string_list(a_val, b_val)
            if merged_list:
                result[field] = merged_list
            else:
                result.pop(field, None)

    # prefer-nonempty fields
    for field in _PREFER_NONEMPTY_FIELDS:
        a_val = meta_a.get(field)
        b_val = meta_b.get(field)
        if field == "oompah.task_costs":
            merged = _merge_oompah_costs(a_val, b_val)
            if merged is not None:
                result[field] = merged
        else:
            if a_val and not b_val:
                result[field] = a_val
            elif b_val and not a_val:
                result[field] = b_val
            elif a_val and b_val:
                # Both set: prefer newer-date side (already in result from newer_meta)
                pass

    return result


def _extract_comments(body: str) -> list[str]:
    """Extract raw comment blocks (including markers) from a task body."""
    comments = []
    pattern = re.compile(
        r"<!-- COMMENT:BEGIN -->\n.*?<!-- COMMENT:END -->",
        re.DOTALL,
    )
    for match in pattern.finditer(body):
        comments.append(match.group(0))
    return comments


def _comment_index(block: str) -> int:
    """Extract the numeric index from a comment block, or 0 if not found."""
    m = re.search(r"^index:\s*(\d+)\s*$", block, re.MULTILINE)
    return int(m.group(1)) if m else 0


def _merge_body_comments(body_a: str, body_b: str) -> str:
    """Merge comment blocks from two body strings.

    Returns *body_a* with any comments from *body_b* that are not in *body_a*
    appended before the COMMENTS:END marker (or at the end of body).
    """
    comments_a = _extract_comments(body_a)
    comments_b = _extract_comments(body_b)

    # Dedup by content (normalized whitespace)
    def norm(c: str) -> str:
        return re.sub(r"\s+", " ", c).strip()

    seen = {norm(c) for c in comments_a}
    new_comments = [c for c in comments_b if norm(c) not in seen]

    if not new_comments:
        return body_a

    # Insert new comments before COMMENTS:END
    end_marker = "<!-- COMMENTS:END -->"
    pos = body_a.find(end_marker)
    if pos >= 0:
        prefix = body_a[:pos]
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        suffix = body_a[pos:]
        return prefix + "".join(c + "\n" for c in new_comments) + suffix

    # No COMMENTS:END — append at end
    result = body_a.rstrip("\n")
    if not comments_a:
        # No comment section yet — create one
        result += "\n\n## Comments\n<!-- COMMENTS:BEGIN -->\n"
    result += "".join(c + "\n" for c in new_comments)
    if "<!-- COMMENTS:END -->" not in body_a:
        result += "<!-- COMMENTS:END -->\n"
    return result


def _resolve_conflict_blocks(content: str) -> str | None:
    """Resolve all conflict blocks in *content* using structured frontmatter merge.

    Returns the resolved content string, or None if resolution is not safe
    (e.g. conflicts span the YAML frontmatter delimiters, or YAML cannot
    be parsed from either side).

    The function handles:
    - Conflict markers entirely within the frontmatter section.
    - Conflict markers entirely within the body section.
    - Simple single-block frontmatter conflicts (most common case).
    """
    if not has_conflict_markers(content):
        return content  # Nothing to do

    # Try to split content into frontmatter and body
    # The tricky part is that the `---` delimiters themselves may be in a
    # conflict block. For safety, we only handle the case where the outer
    # structure is intact.
    if not content.startswith("---\n"):
        logger.debug("Conflict in non-frontmatter file — not safe to repair")
        return None

    # Find the closing frontmatter delimiter
    # It must be a line that is exactly `---` (not inside conflict markers)
    # We look for `\n---\n` or `\n---` at end-of-file OUTSIDE conflict blocks.
    # Simple heuristic: find lines that are exactly `---` which are not
    # immediately inside a conflict block.
    lines = content.split("\n")
    # Find the frontmatter end: first `---` line after line 0 that is not
    # inside a conflict block
    in_conflict = False
    fm_end_line: int | None = None
    for i, line in enumerate(lines):
        if i == 0:  # first `---`
            continue
        if line.startswith("<<<<<<<"):
            in_conflict = True
        elif line.startswith(">>>>>>>"):
            in_conflict = False
        elif line == "---" and not in_conflict:
            fm_end_line = i
            break

    if fm_end_line is None:
        logger.debug("Cannot find frontmatter end delimiter — not safe to repair")
        return None

    frontmatter_raw = "\n".join(lines[1:fm_end_line])
    body_raw = "\n".join(lines[fm_end_line + 1:])

    # --- Resolve frontmatter conflicts ---
    resolved_frontmatter: str | None = None
    if has_conflict_markers(frontmatter_raw):
        resolved_frontmatter = _resolve_frontmatter_conflict(frontmatter_raw)
        if resolved_frontmatter is None:
            return None  # Cannot safely repair
    else:
        resolved_frontmatter = frontmatter_raw

    # --- Resolve body conflicts ---
    resolved_body: str | None = None
    if has_conflict_markers(body_raw):
        resolved_body = _resolve_body_conflict(body_raw)
        if resolved_body is None:
            return None  # Cannot safely repair
    else:
        resolved_body = body_raw

    # Reconstruct the file
    reconstructed = f"---\n{resolved_frontmatter}\n---\n{resolved_body}"
    # Ensure trailing newline
    if not reconstructed.endswith("\n"):
        reconstructed += "\n"
    return reconstructed


def _resolve_frontmatter_conflict(frontmatter: str) -> str | None:
    """Resolve git conflict markers within a YAML frontmatter block.

    Returns the resolved YAML string, or None if resolution cannot be done safely.
    """
    # Find all conflict blocks
    blocks = list(_CONFLICT_BLOCK_RE.finditer(frontmatter))
    if not blocks:
        # Has markers but no complete blocks — unsafe
        return None

    # We currently support the case where the ENTIRE frontmatter is one
    # conflict block, or where individual key-value lines are conflicted.
    # For simplicity, if there's exactly one block covering the whole
    # frontmatter, do a full YAML-level merge.
    if len(blocks) == 1:
        block = blocks[0]
        ours_text = block.group(1)
        theirs_text = block.group(2)

        # Try to parse both sides
        try:
            meta_a = yaml.safe_load(ours_text) or {}
            meta_b = yaml.safe_load(theirs_text) or {}
        except yaml.YAMLError as exc:
            logger.debug("Cannot parse YAML from conflict sides: %s", exc)
            return None

        if not isinstance(meta_a, dict) or not isinstance(meta_b, dict):
            return None

        merged = _merge_frontmatter(meta_a, meta_b)
        try:
            return yaml.safe_dump(merged, sort_keys=False, allow_unicode=False)
        except yaml.YAMLError as exc:
            logger.debug("Cannot serialize merged YAML: %s", exc)
            return None

    # Multiple conflict blocks — try to resolve line-by-line
    # Replace each conflict block by taking the ours side (conservative)
    resolved = frontmatter
    for block in reversed(blocks):  # reverse to preserve positions
        ours = block.group(1)
        theirs = block.group(2)
        # For individual-line conflicts, try YAML-level merge if both are dicts
        try:
            meta_a = yaml.safe_load(ours) or {}
            meta_b = yaml.safe_load(theirs) or {}
        except yaml.YAMLError:
            # Can't parse these individual lines as YAML — take ours
            resolved = resolved[: block.start()] + ours + resolved[block.end():]
            continue

        if isinstance(meta_a, dict) and isinstance(meta_b, dict):
            merged = _merge_frontmatter(meta_a, meta_b)
            try:
                merged_text = yaml.safe_dump(merged, sort_keys=False, allow_unicode=False).rstrip("\n")
            except yaml.YAMLError:
                merged_text = ours
        else:
            merged_text = ours

        resolved = resolved[: block.start()] + merged_text + resolved[block.end():]

    # Verify the result is valid YAML
    try:
        parsed = yaml.safe_load(resolved)
        if not isinstance(parsed, dict):
            return None
    except yaml.YAMLError:
        return None

    return resolved


def _resolve_body_conflict(body: str) -> str | None:
    """Resolve git conflict markers in a task body.

    For body conflicts, we merge comments from both sides and take the
    ours side for everything else (description, sections).
    Returns the resolved body string, or None if resolution is unsafe.
    """
    blocks = list(_CONFLICT_BLOCK_RE.finditer(body))
    if not blocks:
        return None

    # For each conflict block: extract comments from both sides and merge
    resolved = body
    for block in reversed(blocks):
        ours_body = block.group(1)
        theirs_body = block.group(2)
        # Merge comments from both sides
        merged = _merge_body_comments(ours_body, theirs_body)
        resolved = resolved[: block.start()] + merged + resolved[block.end():]

    return resolved


def repair_backlog_task_file(path: Path) -> bool:
    """Attempt to auto-repair a git-conflicted Backlog.md task file in-place.

    Reads the file, resolves conflict markers using structured merge rules,
    validates the result with YAML parsing, and writes the repaired content
    back to disk.

    Returns:
        True  — repair succeeded; file is now conflict-free and valid.
        False — repair was skipped (not conflicted) or failed (unsafe).
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read task file for repair %s: %s", path, exc)
        return False

    if not has_conflict_markers(content):
        return False  # Nothing to do — not an error

    logger.info("Attempting auto-repair of conflicted Backlog task file: %s", path)

    resolved = _resolve_conflict_blocks(content)
    if resolved is None:
        logger.warning(
            "Cannot safely auto-repair %s — conflict is too complex or spans "
            "non-frontmatter structure.",
            path,
        )
        return False

    # Validate the repaired content
    if not _validate_task_content(resolved):
        logger.warning(
            "Repaired content for %s failed YAML validation — not writing.",
            path,
        )
        return False

    # Write repaired content back
    try:
        path.write_text(resolved, encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot write repaired task file %s: %s", path, exc)
        return False

    logger.info("Auto-repaired Backlog conflict in %s", path)
    return True


def _validate_task_content(content: str) -> bool:
    """Return True if *content* is a parseable Backlog.md task file."""
    if not content.startswith("---\n"):
        return False
    end = content.find("\n---", 4)
    if end == -1:
        return False
    frontmatter = content[4:end]
    try:
        meta = yaml.safe_load(frontmatter)
    except yaml.YAMLError:
        return False
    if not isinstance(meta, dict):
        return False
    # Must have no conflict markers in the resolved content
    if has_conflict_markers(content):
        return False
    return True


_BACKLOG_TASK_SUBDIRS = ("tasks", "completed", "archive/tasks")


def _is_backlog_task_markdown_path(rel: str) -> bool:
    """Return True for Backlog task markdown files oompah can repair."""
    if not rel.endswith(".md"):
        return False
    norm = f"/{rel.replace(chr(92), '/')}"
    return any(
        f"/{backlog_name}/{subdir}/" in norm
        for backlog_name in ("backlog", ".backlog")
        for subdir in _BACKLOG_TASK_SUBDIRS
    )


def _backlog_task_dirs(repo_path: str) -> list[str]:
    """Return candidate backlog task directories within *repo_path*."""
    dirs = []
    for backlog_name in ("backlog", ".backlog"):
        for sub in _BACKLOG_TASK_SUBDIRS:
            d = os.path.join(repo_path, backlog_name, sub)
            if os.path.isdir(d):
                dirs.append(d)
    return dirs


def inspect_repo_backlog_conflicts(repo_path: str) -> list[str]:
    """Return paths of backlog task files that contain git conflict markers.

    Scans ``<repo>/backlog/tasks/`` and ``<repo>/backlog/completed/`` (and
    ``.backlog/`` variants) for ``*.md`` files with ``<<<<<<<`` markers.

    This is the primary entry point for pre-dispatch conflict detection.
    """
    conflicted: list[str] = []
    for task_dir in _backlog_task_dirs(repo_path):
        try:
            entries = os.listdir(task_dir)
        except OSError:
            continue
        for name in sorted(entries):
            if not name.endswith(".md"):
                continue
            fpath = os.path.join(task_dir, name)
            try:
                content = Path(fpath).read_text(encoding="utf-8")
            except OSError:
                continue
            if has_conflict_markers(content):
                conflicted.append(fpath)

    if conflicted:
        logger.info(
            "Detected %d conflicted Backlog task file(s) in %s: %s",
            len(conflicted),
            repo_path,
            ", ".join(os.path.basename(f) for f in conflicted[:5])
            + (" ..." if len(conflicted) > 5 else ""),
        )
    return conflicted


def repair_repo_backlog_conflicts(
    repo_path: str,
) -> dict[str, list[str]]:
    """Attempt auto-repair of all conflicted Backlog task files in *repo_path*.

    Returns::

        {
            "repaired": ["/abs/path/to/file.md", ...],  # successfully repaired
            "failed":   ["/abs/path/to/file.md", ...],  # repair failed/unsafe
        }
    """
    conflicted = inspect_repo_backlog_conflicts(repo_path)
    repaired: list[str] = []
    failed: list[str] = []

    for fpath in conflicted:
        ok = repair_backlog_task_file(Path(fpath))
        if ok:
            repaired.append(fpath)
        else:
            failed.append(fpath)

    return {"repaired": repaired, "failed": failed}


# ---------------------------------------------------------------------------
# Unmerged-index recovery (markerless conflicts)
# ---------------------------------------------------------------------------
#
# A failed ``git pull --autostash`` (the routine sync path) can leave a backlog
# task file as an UNMERGED INDEX ENTRY with NO textual conflict markers in the
# working tree (e.g. an add/add or content-identical stage collision). Such an
# entry is invisible to the marker-based scanners above, yet it makes EVERY
# subsequent ``git pull`` fail with "you have unmerged files" — so the managed
# checkout silently falls behind origin with no quarantine/alert. These helpers
# detect and recover that state by reconstructing the conflict from git's index
# stages and structured-merging them, then marking the path resolved.


def _run_git(args: list[str], repo_path: str) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return p.returncode, p.stdout, p.stderr
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, "", str(exc)


def clear_colliding_untracked_backlog(
    repo_path: str, remote_ref: str
) -> list[str]:
    """Remove untracked backlog task files that collide with a tracked file on
    ``remote_ref``, so ``git pull`` isn't aborted by "untracked working tree
    files would be overwritten by merge".

    oompah routinely creates task files locally before they're committed; if
    the same path later arrives from origin as a tracked file, the FF merge
    aborts and the checkout silently stalls behind origin. Origin is
    authoritative for tracked files, so the local untracked copy is a
    redundant pre-creation — dropping it lets the canonical version land.
    Scoped to backlog ``*.md`` so code / build artifacts are never touched.

    Returns the list of removed absolute paths.
    """
    rc, out, _ = _run_git(
        ["ls-files", "--others", "--exclude-standard", "-z", "--", "backlog", ".backlog"],
        repo_path,
    )
    if rc != 0 or not out:
        return []
    removed: list[str] = []
    for rel in out.split("\0"):
        if not rel or not rel.endswith(".md"):
            continue
        # Does a tracked file at this path exist on the incoming ref?
        rc2, _, _ = _run_git(["cat-file", "-e", f"{remote_ref}:{rel}"], repo_path)
        if rc2 != 0:
            continue
        try:
            os.remove(os.path.join(repo_path, rel))
            removed.append(os.path.join(repo_path, rel))
        except OSError as exc:
            logger.warning("Cannot remove colliding untracked %s: %s", rel, exc)
    if removed:
        logger.info(
            "Cleared %d colliding untracked backlog file(s) in %s before pull: %s",
            len(removed),
            repo_path,
            ", ".join(os.path.basename(p) for p in removed[:5]),
        )
    return removed


def _git_show_stage(repo_path: str, stage: int, relpath: str) -> str | None:
    """Return the content of ``relpath`` at merge ``stage`` (1=base, 2=ours,
    3=theirs), or None if that stage does not exist."""
    rc, out, _ = _run_git(["show", f":{stage}:{relpath}"], repo_path)
    return out if rc == 0 else None


def inspect_repo_unmerged_backlog(repo_path: str) -> list[str]:
    """Return absolute paths of UNMERGED backlog task files (``git ls-files -u``).

    Unlike :func:`inspect_repo_backlog_conflicts`, this catches markerless
    unmerged-index entries that block ``git pull``.
    """
    rc, out, _ = _run_git(["ls-files", "-u", "-z"], repo_path)
    if rc != 0 or not out:
        return []
    rels: set[str] = set()
    for entry in out.split("\0"):
        if not entry:
            continue
        # format: "<mode> <sha> <stage>\t<path>"
        tab = entry.find("\t")
        if tab == -1:
            continue
        rel = entry[tab + 1 :]
        rels.add(rel)
    out_paths: list[str] = []
    for rel in sorted(rels):
        if _is_backlog_task_markdown_path(rel):
            out_paths.append(os.path.join(repo_path, rel))
    return out_paths


def _merge_task_versions(ours: str, theirs: str) -> str | None:
    """Structured-merge two complete task-file versions (no markers needed).

    Reuses the same frontmatter + comment merge rules as the marker-based
    repair. Returns the merged file content, or None if either side is
    unparseable / the result is invalid.
    """
    def split(content: str) -> tuple[str, str] | None:
        if not content.startswith("---\n"):
            return None
        end = content.find("\n---", 4)
        if end == -1:
            return None
        return content[4:end], content[end + 4 :]  # (frontmatter, body-after-fence)

    so = split(ours)
    st = split(theirs)
    if so is None or st is None:
        return None
    fm_o, body_o = so
    fm_t, body_t = st
    try:
        meta_o = yaml.safe_load(fm_o) or {}
        meta_t = yaml.safe_load(fm_t) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(meta_o, dict) or not isinstance(meta_t, dict):
        return None
    merged_meta = _merge_frontmatter(meta_o, meta_t)
    merged_body = _merge_body_comments(body_o, body_t)
    try:
        fm_text = yaml.safe_dump(merged_meta, sort_keys=False, allow_unicode=False)
    except yaml.YAMLError:
        return None
    result = "---\n" + fm_text + "---" + merged_body
    return result if _validate_task_content(result) else None


def recover_repo_unmerged_backlog(repo_path: str) -> dict[str, list[str]]:
    """Recover markerless unmerged-index backlog files so ``git pull`` works.

    For each unmerged backlog file, reconstruct the two sides from the index
    stages and structured-merge them (preferring a both-sides merge; falling
    back to whichever stage exists, or a clean working-tree copy). On success
    the file is rewritten and ``git add``-ed to clear the unmerged state.

    Returns ``{"recovered": [...], "failed": [...]}`` (absolute paths).
    """
    recovered: list[str] = []
    failed: list[str] = []
    unmerged = inspect_repo_unmerged_backlog(repo_path)
    if not unmerged:
        return {"recovered": recovered, "failed": failed}

    for abspath in unmerged:
        rel = os.path.relpath(abspath, repo_path)
        ours = _git_show_stage(repo_path, 2, rel)
        theirs = _git_show_stage(repo_path, 3, rel)

        merged: str | None = None
        if ours is not None and theirs is not None:
            merged = _merge_task_versions(ours, theirs)
        elif ours is not None and _validate_task_content(ours):
            merged = ours
        elif theirs is not None and _validate_task_content(theirs):
            merged = theirs

        if merged is None:
            # Last resort: a clean, valid working-tree copy (no markers).
            try:
                wt = Path(abspath).read_text(encoding="utf-8")
            except OSError:
                wt = ""
            if wt and not has_conflict_markers(wt) and _validate_task_content(wt):
                merged = wt

        if merged is None:
            failed.append(abspath)
            continue

        try:
            Path(abspath).write_text(merged, encoding="utf-8")
        except OSError as exc:
            logger.warning("Cannot write recovered task file %s: %s", abspath, exc)
            failed.append(abspath)
            continue
        rc, _, err = _run_git(["add", "--", rel], repo_path)
        if rc != 0:
            logger.warning("git add failed for recovered %s: %s", abspath, err[:200])
            failed.append(abspath)
            continue
        recovered.append(abspath)

    if recovered:
        logger.info(
            "Recovered %d unmerged backlog file(s) in %s: %s",
            len(recovered),
            repo_path,
            ", ".join(os.path.basename(p) for p in recovered[:5]),
        )
    if failed:
        logger.warning(
            "Could not recover %d unmerged backlog file(s) in %s: %s",
            len(failed),
            repo_path,
            ", ".join(os.path.basename(p) for p in failed[:5]),
        )
    return {"recovered": recovered, "failed": failed}


# ---------------------------------------------------------------------------
# Invalid task file detection and recovery (zero-byte / malformed frontmatter)
# ---------------------------------------------------------------------------
#
# A disk-full event can truncate tracked Backlog task files to zero bytes or
# leave them with partial content that has no valid YAML frontmatter.  Unlike
# git conflict markers these files look structurally fine to git (no unmerged
# index entries, no <<< markers) so they pass all existing soundness checks
# while Backlog parses them as empty or invalid tasks.
#
# The helpers below detect such files and attempt to restore them from git's
# object store (HEAD, then origin/<branch>) before the soundness check runs.
# Unrecoverable tracked files are returned so the caller can quarantine the
# project.  Zero-byte untracked files that have no git counterpart are removed
# as spurious artifacts.


def inspect_repo_invalid_backlog_task_files(repo_path: str) -> list[str]:
    """Return absolute paths of Backlog task files that are zero-byte or have
    missing/malformed YAML frontmatter.

    Conflict-marker files are excluded — those are handled by
    :func:`inspect_repo_backlog_conflicts` / :func:`repair_repo_backlog_conflicts`.
    Only files that fail :func:`_validate_task_content` are reported, so
    legitimate non-task markdown files that happen to sit in a backlog
    sub-directory (e.g. README.md without frontmatter) are also caught if they
    are in the task/completed/archive-tasks directories.
    """
    invalid: list[str] = []
    for task_dir in _backlog_task_dirs(repo_path):
        try:
            entries = os.listdir(task_dir)
        except OSError:
            continue
        for name in sorted(entries):
            if not name.endswith(".md"):
                continue
            fpath = os.path.join(task_dir, name)
            try:
                content = Path(fpath).read_text(encoding="utf-8")
            except OSError:
                continue
            # Conflict-marker files are handled by repair_repo_backlog_conflicts
            if has_conflict_markers(content):
                continue
            # Detect zero-byte or missing/malformed frontmatter
            if not content.strip() or not _validate_task_content(content):
                invalid.append(fpath)

    if invalid:
        logger.info(
            "Detected %d invalid (zero-byte/malformed) Backlog task file(s)"
            " in %s: %s",
            len(invalid),
            repo_path,
            ", ".join(os.path.basename(f) for f in invalid[:5])
            + (" ..." if len(invalid) > 5 else ""),
        )
    return invalid


def recover_invalid_backlog_task_files(
    repo_path: str, remote: str = "origin", remote_branch: str = "main"
) -> dict[str, list[str]]:
    """Attempt to recover zero-byte or malformed Backlog task files from git.

    For each invalid file detected by
    :func:`inspect_repo_invalid_backlog_task_files`, tries in order:

    1. ``git show HEAD:<relpath>`` — the last committed local version.
    2. ``git show <remote>/<remote_branch>:<relpath>`` — the remote canonical
       version.

    If a valid version is found it is written back to disk and staged with
    ``git add``.

    For zero-byte files that have **no git counterpart** (untracked and not in
    HEAD or the remote ref), the file is removed as a spurious artifact — it
    was never a valid task and cannot be recovered.

    Unrecoverable **tracked** files (tracked in git but invalid at every
    available ref) are left unchanged and returned in ``"failed"`` so the
    caller can quarantine the project.

    Returns ``{"recovered": [...], "failed": [...], "removed": [...]}``
    (absolute paths).
    """
    recovered: list[str] = []
    failed: list[str] = []
    removed: list[str] = []

    invalid = inspect_repo_invalid_backlog_task_files(repo_path)
    if not invalid:
        return {"recovered": recovered, "failed": failed, "removed": removed}

    for abspath in invalid:
        rel = os.path.relpath(abspath, repo_path)

        # Try HEAD first (preserves local committed state), then remote
        restored: str | None = None
        for ref in (f"HEAD:{rel}", f"{remote}/{remote_branch}:{rel}"):
            rc, out, _ = _run_git(["show", ref], repo_path)
            if rc == 0 and out and _validate_task_content(out):
                restored = out
                break

        if restored is not None:
            try:
                Path(abspath).write_text(restored, encoding="utf-8")
            except OSError as exc:
                logger.warning(
                    "Cannot write recovered task file %s: %s", abspath, exc
                )
                failed.append(abspath)
                continue

            rc_add, _, err = _run_git(["add", "--", rel], repo_path)
            if rc_add != 0:
                logger.warning(
                    "git add failed for recovered invalid file %s: %s",
                    abspath,
                    err[:200],
                )
                failed.append(abspath)
                continue

            logger.info(
                "Recovered invalid (zero-byte/malformed) backlog task file: %s",
                abspath,
            )
            recovered.append(abspath)
            continue

        # No valid version in git — check if the file is tracked at all
        rc_ls, ls_out, _ = _run_git(["ls-files", "--", rel], repo_path)
        is_tracked = rc_ls == 0 and ls_out.strip() != ""

        if not is_tracked:
            # Untracked zero-byte/invalid file with no git counterpart.
            # Remove it as a spurious artifact rather than quarantining.
            try:
                os.remove(abspath)
                logger.info(
                    "Removed spurious untracked invalid backlog file: %s", abspath
                )
                removed.append(abspath)
            except OSError as exc:
                logger.warning(
                    "Cannot remove spurious untracked file %s: %s", abspath, exc
                )
                # Not tracked, so don't quarantine — just warn
        else:
            logger.warning(
                "Cannot recover invalid backlog task file %s — "
                "neither HEAD nor %s/%s has a valid version.",
                abspath,
                remote,
                remote_branch,
            )
            failed.append(abspath)

    if recovered:
        logger.info(
            "Recovered %d invalid backlog task file(s) in %s: %s",
            len(recovered),
            repo_path,
            ", ".join(os.path.basename(p) for p in recovered[:5]),
        )
    if removed:
        logger.info(
            "Removed %d spurious untracked invalid backlog file(s) in %s: %s",
            len(removed),
            repo_path,
            ", ".join(os.path.basename(p) for p in removed[:5]),
        )
    if failed:
        logger.warning(
            "Could not recover %d invalid backlog task file(s) in %s: %s",
            len(failed),
            repo_path,
            ", ".join(os.path.basename(p) for p in failed[:5]),
        )
    return {"recovered": recovered, "failed": failed, "removed": removed}


# ---------------------------------------------------------------------------
# Aggressive whole-checkout self-heal
# ---------------------------------------------------------------------------
#
# The individual recovery helpers above each address one failure mode.
# ``ensure_repo_sound`` chains them into a single, aggressive, AUTOMATIC pass
# that drives a managed checkout back to a sound state every time it runs —
# because oompah's users can't see (let alone fix) a wedged checkout. "Sound"
# means: on the default branch, no in-progress merge/rebase, no unmerged-index
# entries, no conflict markers, and fast-forwarded to the remote default
# branch. As a last resort it hard-resets to the authoritative remote ref —
# but only when doing so cannot lose unpushed NON-backlog (i.e. code) commits;
# otherwise it reports the checkout unrecoverable so the caller quarantines.


def _current_branch(repo_path: str) -> str:
    rc, out, _ = _run_git(["symbolic-ref", "--short", "HEAD"], repo_path)
    return out.strip() if rc == 0 else ""


def _rev_count(repo_path: str, rangespec: str) -> int:
    rc, out, _ = _run_git(["rev-list", "--count", rangespec], repo_path)
    try:
        return int(out.strip()) if rc == 0 else 0
    except ValueError:
        return 0


def list_unmerged_paths(repo_path: str) -> list[str]:
    """All unmerged-index paths (any kind), not just backlog."""
    rc, out, _ = _run_git(["ls-files", "-u", "-z"], repo_path)
    if rc != 0 or not out:
        return []
    paths: set[str] = set()
    for entry in out.split("\0"):
        if not entry:
            continue
        tab = entry.find("\t")
        if tab != -1:
            paths.add(entry[tab + 1 :])
    return sorted(paths)


def _is_backlog_path(rel: str) -> bool:
    norm = f"/{rel.replace(chr(92), '/')}"
    return "/backlog/" in norm or "/.backlog/" in norm


def ensure_repo_sound(
    repo_path: str, default_branch: str, remote: str = "origin"
) -> dict[str, Any]:
    """Aggressively heal a managed checkout to a sound state. Idempotent.

    Returns ``{"sound": bool, "actions": [str], "unrecoverable": [str],
    "reset": bool}``. Best-effort: never raises on git errors.
    """
    actions: list[str] = []
    git_dir = os.path.join(repo_path, ".git")
    if not os.path.isdir(git_dir):
        return {"sound": False, "actions": [], "unrecoverable": [], "reset": False}

    remote_ref = f"{remote}/{default_branch}"

    # 1. Abort any stranded in-progress merge/rebase (leftover from a crash or
    #    a failed autostash pop) — these block everything downstream.
    if os.path.exists(os.path.join(git_dir, "MERGE_HEAD")):
        _run_git(["merge", "--abort"], repo_path)
        actions.append("merge-abort")
    if os.path.isdir(os.path.join(git_dir, "rebase-merge")) or os.path.isdir(
        os.path.join(git_dir, "rebase-apply")
    ):
        _run_git(["rebase", "--abort"], repo_path)
        actions.append("rebase-abort")

    # 2. Fetch the latest remote state.
    _run_git(["fetch", remote], repo_path)

    # 3. Clear untracked backlog files that would block the pull.
    if clear_colliding_untracked_backlog(repo_path, remote_ref):
        actions.append("clear-untracked")

    # 4. Recover markerless unmerged-index backlog entries.
    if recover_repo_unmerged_backlog(repo_path).get("recovered"):
        actions.append("recover-unmerged")

    # 5. Repair textual conflict markers in backlog files.
    if repair_repo_backlog_conflicts(repo_path).get("repaired"):
        actions.append("repair-markers")

    # 5b. Detect and recover zero-byte or malformed-frontmatter backlog files.
    #     These arise after disk-full events and are invisible to the conflict-
    #     marker scanners above.  Tracked files are restored from HEAD or the
    #     remote ref; spurious untracked zero-byte files are removed.
    _invalid_result = recover_invalid_backlog_task_files(repo_path, remote, default_branch)
    if _invalid_result.get("recovered"):
        actions.append("recover-invalid")
    if _invalid_result.get("removed"):
        actions.append("remove-spurious")

    # 6. Make sure we're on the default branch.
    if _current_branch(repo_path) != default_branch:
        if _run_git(["checkout", default_branch], repo_path)[0] == 0:
            actions.append("checkout-default")

    # 7. Fast-forward to the remote default branch (autostash tracked edits).
    rc, _, _ = _run_git(
        ["pull", "--ff-only", "--autostash", remote, default_branch], repo_path
    )
    if rc == 0:
        actions.append("ff-pull")
    else:
        # A conflicted autostash pop may have produced fresh unmerged entries.
        if recover_repo_unmerged_backlog(repo_path).get("recovered"):
            actions.append("recover-postpull")

    def _sound() -> bool:
        return (
            not list_unmerged_paths(repo_path)
            and _rev_count(repo_path, f"HEAD..{remote_ref}") == 0
            and not inspect_repo_backlog_conflicts(repo_path)
            and not inspect_repo_invalid_backlog_task_files(repo_path)
            and _current_branch(repo_path) == default_branch
        )

    if _sound():
        return {"sound": True, "actions": actions, "unrecoverable": [], "reset": False}

    # 8. Last resort: hard-reset to the authoritative remote ref — but ONLY
    #    when there is genuinely nothing to lose.
    #
    #    A managed checkout holds oompah's AND the operator's task-status edits
    #    as UNCOMMITTED working-tree changes (e.g. dragging a card to "Open" in
    #    the dashboard). A blind hard-reset silently reverts those to origin's
    #    baseline — regressing statuses back to Backlog. That is never
    #    acceptable. So reset is permitted only when the working tree is clean
    #    AND nothing is unpushed. The structured recovery in steps 3–7 already
    #    preserves status across conflicts (more-advanced status wins); if the
    #    checkout still isn't sound while carrying uncommitted/unpushed work, we
    #    report it unrecoverable so the caller quarantines + alerts — loud, but
    #    never a silent data-loss reset.
    rc, dirty_out, _ = _run_git(["status", "--porcelain"], repo_path)
    working_tree_clean = rc == 0 and not dirty_out.strip()
    unpushed = _rev_count(repo_path, f"{remote_ref}..HEAD")

    if working_tree_clean and unpushed == 0:
        _run_git(["reset", "--hard", remote_ref], repo_path)
        actions.append("hard-reset")
        sound = _sound()
        if not sound:
            _unrec = list(list_unmerged_paths(repo_path))
            for p in inspect_repo_invalid_backlog_task_files(repo_path):
                if p not in _unrec:
                    _unrec.append(p)
        return {
            "sound": sound,
            "actions": actions,
            "unrecoverable": [] if sound else _unrec,
            "reset": True,
        }

    # 9. Not sound but carrying uncommitted or unpushed work — preserve it and
    #    quarantine rather than reset.
    unrec = list_unmerged_paths(repo_path) or [
        f"unsound: dirty/divergent checkout at {repo_path} "
        f"({unpushed} unpushed, dirty={not working_tree_clean})"
    ]
    # Also include any remaining invalid task files (zero-byte/malformed).
    for p in inspect_repo_invalid_backlog_task_files(repo_path):
        if p not in unrec:
            unrec.append(p)
    logger.warning(
        "Checkout %s not sound; preserving uncommitted/unpushed work and "
        "quarantining (no destructive reset). actions=%s",
        repo_path,
        ",".join(actions) or "none",
    )
    return {
        "sound": False,
        "actions": actions,
        "unrecoverable": unrec,
        "reset": False,
    }
