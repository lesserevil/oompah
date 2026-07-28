---
id: OOMPAH-455
type: bug
status: In Progress
priority: 1
title: Make GitLab project edits use one intake alias and forge-aware identity resolution
parent: OOMPAH-451
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T12:34:53.400428Z'
updated_at: '2026-07-28T13:31:25.552595Z'
work_branch: epic-OOMPAH-451
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a00f7998-b980-4554-9182-88df0e639877
oompah.work_branch: epic-OOMPAH-451
oompah.task_costs:
  total_input_tokens: 28
  total_output_tokens: 6141
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 28
      output_tokens: 6141
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 28
    output_tokens: 6141
    cost_usd: 0.0
    recorded_at: '2026-07-28T13:31:08.641652+00:00'
---
## Summary

Problem: the Projects editor always sends both github_issue_intake_enabled and external_issue_intake_enabled. ProjectStore explicitly rejects both, so any edit, including enabling state_branch_enabled, fails with Specify only one error even when both values are false and equal. The same save path also calls the GitHub token-owner API when status_actor_login is blank, generating GitHub 401 warnings for a valid GitLab token.

Implementation scope: send one canonical forge-neutral intake field from oompah/templates/projects.html; make the PATCH compatibility contract deterministic for legacy and neutral clients; resolve actor identity with the configured forge provider or leave it unset without calling another forge. Ensure editing unrelated settings does not rewrite or validate unrelated aliases. Relevant files include oompah/templates/projects.html, oompah/server.py, oompah/projects.py, and project CRUD/GitLab UI tests.

Tests: reproduce editing a GitLab project with both stored intake aliases represented in the GET response, enable state_branch_enabled through the UI payload, assert a successful update, and assert no GitHub identity call; cover legacy GitHub clients and conflicting alias values explicitly; run make test.

Acceptance criteria: enabling the state branch for nodevirt succeeds from the Projects page; matching compatibility aliases never block unrelated edits; conflicting values receive a precise validation error; GitLab credentials are never sent to GitHub.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 13:28
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 13:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 13:30
---
Duplicate investigation complete: No duplicate found.

Searched across all .oompah/tasks/ states (archived, merged, open, backlog — 280+ tasks) and plans/ docs/ using keywords: github_issue_intake_enabled, external_issue_intake_enabled, Specify only one, intake alias, forge-aware, forge identity, status_actor_login, state_branch_enabled, nodevirt, Projects editor, GitLab 401, token owner, PATCH project, intake_enabled.

Zero matches across all search patterns. OOMPAH-455 describes a novel bug specific to the Projects UI editor sending both intake alias fields simultaneously, causing ProjectStore validation failure.

Closest candidate reviewed and ruled out:
- plans/gitlab-forge-parity.md — a large design plan that mentions generalizing github_issue_intake_enabled → external_issue_intake_enabled as a future architecture goal, but contains no task or fix for the specific bug described here (simultaneous alias sending blocking unrelated edits).

No existing task covers the same failure mode (ProjectStore rejecting both intake aliases simultaneously, or GitHub 401 warnings from GitLab token resolving via GitHub API).

Relevant files for implementation:
- oompah/templates/projects.html — UI sends both intake fields; needs to send only one canonical forge-neutral field
- oompah/server.py — PATCH handler; needs compatibility alias contract and forge-aware identity resolution
- oompah/projects.py — ProjectStore validation; needs deterministic alias normalization
- tests/ — need GitLab project edit test, legacy GitHub client test, conflicting alias test

Next focus: backend (bug fix + tests)
---
author: oompah
created: 2026-07-28 13:31
---
Agent completed successfully in 140s (6169 tokens)
---
author: oompah
created: 2026-07-28 13:31
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 64, Tool calls: 40
- Tokens: 28 in / 6.1K out [6.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 20s
- Log: OOMPAH-455__20260728T132851Z.jsonl
---
author: oompah
created: 2026-07-28 13:31
---
Focus handoff required before leaving `duplicate_detector`. Add a comment headed `Focus handoff: duplicate_detector` with outcome, evidence, remaining work, and next focus.
---
author: oompah
created: 2026-07-28 13:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 13:31
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
