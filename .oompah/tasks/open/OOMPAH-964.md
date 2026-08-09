---
id: OOMPAH-964
type: bug
status: Open
priority: 1
title: Ignore PR-backed issue comments in GitHub issue intake
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- github-intake
- needs:backend
assignee: null
created_at: '2026-08-09T16:09:40.311061Z'
updated_at: '2026-08-09T16:26:49.965142Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-963

GitHub sends issue_comment webhooks for both issues and pull requests. The 2026-08-09 issue_comment.created deliveries for merged PR #768 were routed through native GitHub issue intake and created erroneous Proposed task OOMPAH-963, even though pull_request events, issues events with an issue.pull_request marker, and GitHub issues-list polling already exclude PRs. Implement defense-in-depth so PR-backed issue_comment payloads can never be normalized or imported as native work. Scope: update oompah/webhooks.py and/or oompah/github_intake_bridge.py at the issue-comment parsing/intake boundary; preserve pull-request review lifecycle handling and ordinary GitHub issue comment synchronization. Add regression coverage in tests/test_webhooks.py and tests/test_github_intake_bridge.py for an issue_comment.created payload whose issue object includes pull_request, proving it creates no native Proposed task and imports no comment, including when a lower-level intake helper is invoked defensively. Keep ordinary issue_comment.created/edited behavior unchanged. Acceptance criteria: (1) PR-backed issue_comment webhooks are ignored by native issue intake without creating or mutating native tasks; (2) PR webhook review handling remains unchanged; (3) genuine issue comments continue to import; (4) regression tests reproduce the PR #768/OOMPAH-963 failure shape and pass; (5) focused webhook and GitHub-intake test modules pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 16:20
---
Project owner promotes the confirmed PR-backed issue_comment intake regression for direct implementation.
---
author: oompah
created: 2026-08-09 16:26
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-964`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`
Process: ended without subprocess exit evidence

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
<!-- COMMENTS:END -->
