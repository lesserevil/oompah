from __future__ import annotations

from pathlib import Path

from oompah.issue_validator import validate_issue


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"


def test_managed_project_issue_templates_exist() -> None:
    assert (TEMPLATE_DIR / "bug_report.yml").is_file()
    assert (TEMPLATE_DIR / "feature_request.yml").is_file()
    assert (TEMPLATE_DIR / "question.yml").is_file()
    assert (TEMPLATE_DIR / "config.yml").is_file()


def test_templates_use_oompah_type_labels() -> None:
    assert 'labels: ["type:bug"]' in (TEMPLATE_DIR / "bug_report.yml").read_text()
    assert 'labels: ["type:feature"]' in (
        TEMPLATE_DIR / "feature_request.yml"
    ).read_text()
    assert 'labels: ["type:task"]' in (TEMPLATE_DIR / "question.yml").read_text()


def test_template_generated_bug_shape_satisfies_validator() -> None:
    body = """
## Problem
The service appears healthy, but new Open issues do not dispatch.

## Steps to Reproduce
1. Start the service.
2. Create or move an issue to Open.
3. Observe that no agent starts.

## Actual Behavior
The UI shows no alerts, but the dispatch loop has stopped ticking.

## Expected Behavior
Oompah should surface an alert and recover or restart the dispatch loop safely.

## Acceptance Criteria
- The stale loop condition is detected.
- A regression test covers the failure.
""".strip()

    result = validate_issue(
        title="Detect stopped dispatch loop",
        description=body,
        issue_type="bug",
    )

    assert result.ready is True
    assert result.missing_fields == []


def test_template_generated_feature_shape_satisfies_validator() -> None:
    body = """
## Problem
Project owners need a guided setup flow instead of editing multiple config files.

## Desired Behavior
Oompah should validate repo access and tracker settings during project setup.

## Acceptance Criteria
- A project can be added through the UI.
- Invalid repo credentials show an actionable error.
- Tests cover the setup flow.
""".strip()

    result = validate_issue(
        title="Add guided project setup",
        description=body,
        issue_type="feature",
    )

    assert result.ready is True
    assert result.missing_fields == []


def test_template_generated_question_shape_satisfies_validator() -> None:
    body = """
## Problem
I need to understand how oompah maps GitHub labels to task states.

## Desired Behavior
The answer should explain the mapping and where it is configured.

## Acceptance Criteria
- The answer is documented in the issue or docs.
- Any discovered follow-up work is linked.
""".strip()

    result = validate_issue(
        title="Explain GitHub issue state mapping",
        description=body,
        issue_type="task",
    )

    assert result.ready is True
    assert result.missing_fields == []
