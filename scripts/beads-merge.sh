#!/usr/bin/env bash
# beads-merge.sh — Custom git merge driver for .beads/issues.jsonl
#
# Git invokes merge drivers with three positional arguments:
#   $1  CURRENT  — path to the current branch's version (ours)
#   $2  BASE     — path to the common ancestor version
#   $3  OTHER    — path to the other branch's version (theirs)
#
# The driver must write the merged result into $1 (in-place) and
# exit 0 on success.  Exit non-zero to signal that git should fall
# back to conflict markers (standard behaviour).
#
# Merge strategy: last-writer-wins per issue id
#   - Parse all three sides as JSONL (one JSON object per line).
#   - For each issue id keep whichever version has the later updated_at.
#   - Comments within an issue are merged as a union deduped by comment id.
#   - The output order is deterministic: sorted by created_at, then id.
#
# Failure mode: if Python 3 is not available or this script exits
# non-zero, git falls back to normal three-way merge with conflict
# markers.  The file is never silently corrupted.
#
# Usage (for humans / tests):
#   ./scripts/beads-merge.sh <current> <base> <other>
#   The merged result is written to <current>.

set -euo pipefail

CURRENT="$1"
# BASE="$2"   # not used by the Python implementation but kept for git compat
OTHER="$3"

# Delegate the actual merge to Python for robust JSON handling.
python3 - "$CURRENT" "$OTHER" <<'PYEOF'
import json
import sys
from pathlib import Path


def parse_jsonl(path: str) -> dict[str, dict]:
    """Parse a JSONL file into a dict keyed by issue id.

    Lines that are blank or not valid JSON are silently skipped so that
    a partially-written file does not abort the whole merge.
    """
    issues: dict[str, dict] = {}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return issues
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "id" in obj:
            issues[obj["id"]] = obj
    return issues


def merge_comments(a_comments: list, b_comments: list) -> list:
    """Return the union of two comment lists, deduped by comment id.

    Where both sides have a comment with the same id the version from
    the side with the later (or equal) created_at is kept; in case of a
    tie we prefer *b* (the OTHER branch) so that freshly-added comments
    win over the local branch.
    """
    seen: dict[str, dict] = {}
    for comment in a_comments + b_comments:
        cid = comment.get("id")
        if cid is None:
            # No id — include unconditionally (append with a synthetic key
            # so it isn't silently dropped).
            cid = f"__noid__{id(comment)}"
        existing = seen.get(cid)
        if existing is None:
            seen[cid] = comment
        else:
            # Keep the one with the later created_at; prefer b on ties.
            existing_ts = existing.get("created_at", "")
            new_ts = comment.get("created_at", "")
            if new_ts >= existing_ts:
                seen[cid] = comment
    # Preserve chronological order within the merged set.
    return sorted(seen.values(), key=lambda c: (c.get("created_at", ""), c.get("id", "")))


def merge_issues(current: dict[str, dict], other: dict[str, dict]) -> dict[str, dict]:
    """Merge two dicts of issues keyed by id.

    Strategy (per issue):
      - If only one side has the issue, keep it.
      - If both sides have it, pick the version with the later updated_at.
      - Always merge comments from both sides (union by comment id).
    """
    all_ids = set(current) | set(other)
    merged: dict[str, dict] = {}
    for issue_id in all_ids:
        a = current.get(issue_id)
        b = other.get(issue_id)

        if a is None:
            merged[issue_id] = b
            continue
        if b is None:
            merged[issue_id] = a
            continue

        # Both sides modified this issue — pick the winner by updated_at.
        a_ts = a.get("updated_at", "")
        b_ts = b.get("updated_at", "")
        if b_ts >= a_ts:
            winner = dict(b)
        else:
            winner = dict(a)

        # Always merge comments from both sides regardless of which won.
        a_comments = a.get("comments") or []
        b_comments = b.get("comments") or []
        merged_comments = merge_comments(a_comments, b_comments)
        winner["comments"] = merged_comments
        # Update comment_count to reflect the merged set.
        winner["comment_count"] = len(merged_comments)

        merged[issue_id] = winner

    return merged


def main() -> None:
    current_path = sys.argv[1]
    other_path = sys.argv[2]

    current = parse_jsonl(current_path)
    other = parse_jsonl(other_path)

    merged = merge_issues(current, other)

    # Deterministic output order: sort by created_at then id.
    ordered = sorted(
        merged.values(),
        key=lambda issue: (issue.get("created_at", ""), issue.get("id", "")),
    )

    output_lines = [json.dumps(issue, ensure_ascii=False, separators=(",", ":")) for issue in ordered]
    Path(current_path).write_text("\n".join(output_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
PYEOF
