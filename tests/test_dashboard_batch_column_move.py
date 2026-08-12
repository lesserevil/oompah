"""Dashboard whole-column moves use the atomic batch API (OOMPAH-1178)."""

from pathlib import Path


def _script() -> str:
    html = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")
    return html[html.index("<script>") : html.rindex("</script>")]


def _function(script: str, name: str) -> str:
    for marker in (f"async function {name}(", f"function {name}("):
        if marker in script:
            break
    start = script.index(marker)
    brace = script.index("{", start)
    depth = 0
    for index in range(brace, len(script)):
        if script[index] == "{":
            depth += 1
        elif script[index] == "}":
            depth -= 1
            if depth == 0:
                return script[brace + 1 : index]
    raise AssertionError(name)


def test_column_drag_calls_one_batch_helper_not_n_single_issue_updates():
    body = _function(_script(), "setupColumnDrag")

    assert "await batchMoveColumn(" in body
    assert "await updateIssue(" not in body
    assert "for (const issue of cardsToMove)" not in body


def test_batch_helper_uses_one_project_scoped_request_and_revision_evidence():
    body = _function(_script(), "batchMoveColumn")

    assert "/tasks/batch-update" in body
    assert body.count("await fetch(") == 1
    assert "expected_revision: issue.authority_revision" in body
    assert "Idempotency-Key" in body
    assert "kind: 'whole_column_move'" in body
    assert "issue.authority_revision = committedIssue.revision" in body
    assert "moveIssueInBoard" in body
    assert body.index("if (!response.ok)") < body.index("moveIssueInBoard")


def test_column_idempotency_key_is_bounded_digest_not_raw_member_list():
    body = _function(_script(), "columnBatchIdempotencyKey")

    assert "Math.imul" in body
    assert "cards.length" in body
    assert "return `dashboard-column:" in body
    assert ":${members}`" not in body


def test_column_header_has_keyboard_fallback_and_accessible_role():
    body = _function(_script(), "setupColumnDrag")

    assert "header.tabIndex = 0" in body
    assert "setAttribute('role', 'button')" in body
    assert "header.addEventListener('keydown'" in body
    assert "e.key !== 'Enter' && e.key !== ' '" in body
