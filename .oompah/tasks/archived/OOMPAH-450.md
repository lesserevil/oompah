---
id: OOMPAH-450
type: task
status: Archived
priority: null
title: Link project bootstrap guide to CLI installation instructions
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-27T21:06:07.569431Z'
updated_at: '2026-08-03T22:24:40.930282Z'
work_branch: OOMPAH-450
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/557
review_number: '557'
merged_at: null
oompah.agent_run_id: 0ca37cf4-2921-415b-93ac-51bbde488940
oompah.task_costs:
  total_input_tokens: 855180
  total_output_tokens: 3523
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 855180
      output_tokens: 3523
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 855180
    output_tokens: 3523
    cost_usd: 0.0
    recorded_at: '2026-07-27T21:09:47.922098+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/557
oompah.review_number: '557'
oompah.work_branch: OOMPAH-450
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-fa548d404175: '2026-08-03T22:24:33.140123+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-450
    target_state: Archived
    evidence_fingerprint: a4e4f8076f93f01757b7baa599b1a9792083a8ba3231c7457d75b7e0a7add4d6
    audit_ids:
    - audit-fe9550ea7f71
    kind: result
    applied: true
    retired_at: '2026-08-03T22:24:33.140133+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-450
    audit_id: audit-fe9550ea7f71
    attempt_id: attempt-fa548d404175
    target_state: Archived
    evidence_fingerprint: a4e4f8076f93f01757b7baa599b1a9792083a8ba3231c7457d75b7e0a7add4d6
    status: Archived
    audit_ids:
    - audit-fe9550ea7f71
    applied: true
    created_at: '2026-08-03T22:24:33.140149+00:00'
    applied_at: '2026-08-03T22:24:39.781519+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-fe9550ea7f71
    project_id: proj-14849f1b
    task_id: OOMPAH-450
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a4e4f8076f93f01757b7baa599b1a9792083a8ba3231c7457d75b7e0a7add4d6
    attempts:
    - version: 1
      attempt_id: attempt-fa548d404175
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a4e4f8076f93f01757b7baa599b1a9792083a8ba3231c7457d75b7e0a7add4d6
      created_at: '2026-08-03T22:18:56.073692+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T22:18:56.073692+00:00'
      branch_key: OOMPAH-450
      verdict: pass
      completed_at: '2026-08-03T22:24:33.139985+00:00'
      ended_at: '2026-08-03T22:24:33.139985+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-03T22:17:14.929682+00:00'
    updated_at: '2026-08-03T22:24:33.139985+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-fa548d404175
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a4e4f8076f93f01757b7baa599b1a9792083a8ba3231c7457d75b7e0a7add4d6
    created_at: '2026-08-03T22:18:56.073692+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T22:18:56.073692+00:00'
    branch_key: OOMPAH-450
---
## Summary

Update docs/project-bootstrap.md to make CLI installation an explicit prerequisite and link to docs/cli-install.md before any project-bootstrap commands. Include installation/verification context sufficient to prevent agents on fresh machines from attempting bootstrap without the oompah executable. Add a regression test that verifies the bootstrap guide retains the install-guide link and prerequisite ordering. Acceptance criteria: the guide links to cli-install.md near the Local CLI instructions, clearly states bootstrap does not install the CLI, and the focused documentation test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-27 21:06
---
Starting implementation. Confirmed docs/project-bootstrap.md currently assumes the oompah executable exists and does not link to docs/cli-install.md. I will add an explicit prerequisite/link before the Local CLI commands and a regression assertion in the existing CLI documentation test suite.
---
author: oompah
created: 2026-07-27 21:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-27 21:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-27 21:08
---
Understanding: I am performing the required duplicate-investigator phase only. I will search existing task records and documentation for prior work covering the project-bootstrap CLI prerequisite/link, inspect plausible task candidates in full, and either archive this task if it is a confirmed duplicate or hand it off without implementation if no duplicate is established.
---
author: oompah
created: 2026-07-27 21:09
---
Discovery: Duplicate screening found no confirmed duplicate. Reviewed OOMPAH-9 (generated managed-project guidance and CLI fallbacks), OOMPAH-31 (bootstrap flow validation), OOMPAH-52 (stale-install upgrade guidance in cli-install/release docs), and OOMPAH-35 (broad onboarding checklist), including their full descriptions and comments. None changes docs/project-bootstrap.md to link cli-install.md as a prerequisite before commands or adds the requested ordering regression. Current evidence: the Local CLI section says the GitHub install includes the bootstrap CLI but has no cli-install.md link and does not explicitly say bootstrap itself does not install the executable.
---
author: oompah
created: 2026-07-27 21:09
---
Focus handoff: duplicate_detector\n\nOutcome: No duplicate confirmed; implementation should proceed.\nEvidence: Closest tasks reviewed were OOMPAH-9, OOMPAH-31, OOMPAH-52, and OOMPAH-35, all with distinct scopes. Relevant files are docs/project-bootstrap.md, docs/cli-install.md, and the existing CLI documentation regression suite in tests/test_cli_release_packaging.py. The prerequisite/link must appear in or immediately before the Local CLI section and before the first project-bootstrap command.\nRemaining work/risks: Update the guide to state explicitly that project bootstrap does not install the oompah CLI, link cli-install.md, include an executable verification step suitable for a fresh machine, add a regression test covering link presence and ordering, then run the focused test and project quality gate. No worktree changes were made during duplicate screening.\nRecommended next focus: docs.
---
author: oompah
created: 2026-07-27 21:09
---
Agent completed successfully in 121s (858703 tokens)
---
author: oompah
created: 2026-07-27 21:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 15
- Tokens: 855.2K in / 3.5K out [858.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 1s
- Log: OOMPAH-450__20260727T210751Z.jsonl
---
author: oompah
created: 2026-07-27 21:09
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-27 21:10
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-27 21:10
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-27 21:10
---
Understanding: I will update docs/project-bootstrap.md so the Local CLI workflow links docs/cli-install.md, explicitly says bootstrap does not install the executable, and verifies the CLI before any bootstrap command. I will add an ordering regression to tests/test_cli_release_packaging.py, validate the documented commands, run focused and full Makefile-backed tests, then commit, push, and close the task.
---
author: oompah
created: 2026-07-27 21:10
---
Discovery: docs/project-bootstrap.md first invokes  in Local CLI without linking cli-install.md, explicitly warning that bootstrap cannot install the CLI, or verifying the executable. docs/cli-install.md already supplies authoritative install and verification instructions. tests/test_cli_release_packaging.py is the existing regression suite for these cross-document CLI guarantees, so I will add the link/prerequisite ordering assertion there.
---
author: oompah
created: 2026-07-27 21:11
---
Implementation: Updated docs/project-bootstrap.md so the Local CLI section says project bootstrap does not install or create the oompah executable, links cli-install.md before any bootstrap invocation, verifies the bootstrap help output, and tells readers to stop and install or upgrade when verification fails. Added a regression test in tests/test_cli_release_packaging.py that enforces prerequisite and link ordering before the first bootstrap command.
---
author: oompah
created: 2026-07-27 21:17
---
Verification: Confirmed the documented oompah project-bootstrap help command lists status, preview, and apply. Focused regression passed (1 passed). Full Makefile test gate passed: 12,112 passed, 39 skipped, 14 warnings in 250.22s. The initial Snap wrapper failure was resolved by invoking the installed uv binary directly with a worktree-local cache; tests then ran through make test as required.
---
author: oompah
created: 2026-07-27 21:19
---
Completion: Delivered and pushed commit ad75513ae on branch OOMPAH-450. The bootstrap guide now links the CLI install guide before all bootstrap commands, states bootstrap does not install the executable, and includes a verified help check with stop-and-install guidance. Added the requested ordering regression. Focused test passed; full make test passed with 12,112 passed and 39 skipped; staged secret scan passed. The whole-tree secret target reports only the pre-existing synthetic GitLab fixture from commit 3247029a9, outside this change. No follow-up work remains.
---
author: oompah
created: 2026-07-27 21:19
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 0, Tool calls: 52
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 9m 41s
- Log: OOMPAH-450__20260727T211002Z.jsonl
---
author: oompah
created: 2026-07-27 21:19
---
Linked project bootstrap to CLI installation prerequisite, added verification guidance, and added regression coverage; full tests passed and commit ad75513ae was pushed.
---
author: oompah
created: 2026-07-27 21:40
---
YOLO: merged PR #557.
---
author: oompah
created: 2026-08-03 22:17
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-03 22:19
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 22:19
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 22:24
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 6657f40c6323dc64e89fb35ff130d76e7b693902
- implementation_commit: ad75513ae60c83e86567fb8b1f26d7983153caeb
- pr_number: 557
- changed_files: docs/project-bootstrap.md, tests/test_cli_release_packaging.py
- regression_test: tests/test_cli_release_packaging.py::test_project_bootstrap_docs_require_cli_install_before_commands
- prerequisite_phrase_present: true
- cli_install_link_present: true
- help_verification_present: true
- days_since_merge: 7
---
<!-- COMMENTS:END -->
