---
id: OOMPAH-52
type: task
status: In Review
priority: null
title: Update oompah uv-tool install to include project-bootstrap support
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T14:20:20.212899Z'
updated_at: '2026-06-22T14:52:12.163063Z'
work_branch: OOMPAH-52
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/349
review_number: '349'
merged_at: null
oompah.agent_run_id: e966e93c-13b9-410c-bf38-578f33b8cda0
oompah.task_costs:
  total_input_tokens: 69
  total_output_tokens: 2217
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 69
      output_tokens: 2217
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 69
    output_tokens: 2217
    cost_usd: 0.0
    recorded_at: '2026-06-22T14:51:21.871460+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/349
oompah.review_number: '349'
oompah.work_branch: OOMPAH-52
oompah.target_branch: main
---
## Summary

Validation in OOMPAH-31 found that the oompah binary installed via 'uv tool install git+https://github.com/lesserevil/oompah' (/home/shedwards/.local/bin/oompah) is an older version that lacks project_bootstrap/ and project_bootstrap_cli.py. Running 'oompah project-bootstrap status .' fails with 'unrecognized arguments: status .' because the installed __main__.py does not have the project-bootstrap dispatch block.\n\nThe development version (python3 -m oompah) works correctly.\n\nAny operator who installed oompah before the project-bootstrap feature was added needs to reinstall:\n  uv tool upgrade oompah\n  # or\n  uv tool install --reinstall git+https://github.com/lesserevil/oompah\n\nThis should be called out in the release notes and operator runbook so operators know to reinstall after 1.0 ships.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 14:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 14:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 14:30
---
Understanding: This issue reports that operators who installed oompah via 'uv tool install' before the project-bootstrap feature was added will have a stale binary that lacks the project_bootstrap/ module and project-bootstrap CLI dispatch. The fix is for operators to reinstall, and we need to document this in release notes and the operator runbook. My role is Duplicate Investigator — I'll first search for existing tasks covering the same ground before doing any implementation.
---
author: oompah
created: 2026-06-22 14:36
---
Discovery: OOMPAH-52 is NOT a duplicate — it was explicitly filed by the OOMPAH-31 agent as a follow-up after discovering the stale binary issue during validation. No other task covers documenting the reinstall requirement for operators. The work is: (1) add an 'Upgrading from pre-1.0 installs' section to docs/cli-install.md covering the project-bootstrap reinstall requirement, and (2) add a note to the release notes section of docs/cli-release.md. There is no operator runbook doc yet (D2 from oompah-1.0-release.md), so I'll focus on the install/release docs where an upgrade notice belongs.
---
author: oompah
created: 2026-06-22 14:47
---
Implementation plan: (1) Add 'Upgrading an existing install' section to docs/cli-install.md — explains that pre-project-bootstrap installs need 'uv tool upgrade oompah' or '--reinstall'. (2) Add upgrade notice to scripts/render_cli_release_notes.py so the 1.0 release notes include the reinstall call-out. (3) Add note in docs/cli-release.md that release notes should call out reinstall requirements for major feature additions. (4) Add test in test_cli_release_packaging.py that verifies the upgrade section appears in generated release notes.
---
author: oompah
created: 2026-06-22 14:50
---
Verification: All 7044 tests pass (make test). The 3 new tests all pass: test_release_notes_include_upgrade_and_reinstall_guidance, test_release_notes_upgrade_section_references_tag_install, test_install_docs_cover_upgrade_from_pre_project_bootstrap_install. Not a duplicate — explicitly filed by OOMPAH-31 as a follow-up.
---
author: oompah
created: 2026-06-22 14:51
---
Completion: Documented the project-bootstrap reinstall requirement for operators with stale uv-tool installs. Delivered: (1) docs/cli-install.md — new 'Upgrading an existing install' section explaining that pre-project-bootstrap installs fail with 'unrecognized arguments: status .' and need 'uv tool upgrade oompah' or '--reinstall'. (2) scripts/render_cli_release_notes.py — added 'Upgrading from an earlier install' section to generated release notes, with reinstall command pinned to the specific release tag; also added 'oompah project-bootstrap --help' to the verify block. (3) docs/cli-release.md — added callout in the Release notes section explaining when to include upgrade guidance and specifically noting the project-bootstrap reinstall requirement. (4) tests/test_cli_release_packaging.py — 3 new tests verifying the upgrade guidance appears in generated release notes and install docs. All 7044 tests pass.
---
author: oompah
created: 2026-06-22 14:51
---
Documented project-bootstrap reinstall requirement in docs/cli-install.md, scripts/render_cli_release_notes.py, and docs/cli-release.md. Added 3 new tests. All 7044 tests pass.
---
author: oompah
created: 2026-06-22 14:51
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 46
- Tokens: 69 in / 2.2K out [2.3K total]
- Cost: $0.0000
- Exit: terminated, Duration: 21m 21s
- Log: OOMPAH-52__20260622T143005Z.jsonl
---
<!-- COMMENTS:END -->
