---
id: OOMPAH-24
type: task
status: In Progress
priority: 1
title: Expand release smoke tests for project-bootstrap
parent: OOMPAH-22
children: []
blocked_by:
- OOMPAH-23
labels: []
assignee: null
created_at: '2026-06-22T01:16:43.935007Z'
updated_at: '2026-06-22T02:35:57.472195Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 6bcd0cde-4072-46d7-b85b-31b283ef127f
oompah.task_costs:
  total_input_tokens: 8226889
  total_output_tokens: 37774
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 8226889
      output_tokens: 37774
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 4371367
    output_tokens: 21280
    cost_usd: 0.0
    recorded_at: '2026-06-22T02:17:21.529731+00:00'
  - profile: standard
    model: unknown
    input_tokens: 3855522
    output_tokens: 16494
    cost_usd: 0.0
    recorded_at: '2026-06-22T02:28:01.677719+00:00'
---
## Summary

Plan: plans/oompah-1.0-release.md#cli-and-api-contract

WHAT TO DO
Expand packaging and release smoke tests to cover oompah project-bootstrap --help in addition to the existing root and task command smoke checks.

HOW TO VERIFY
The release packaging tests fail if project-bootstrap is missing from the installed lightweight CLI.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 02:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:17
---
Agent completed successfully in 750s (4392647 tokens)
---
author: oompah
created: 2026-06-22 02:17
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 66
- Tokens: 4.4M in / 21.3K out [4.4M total]
- Cost: $0.0000
- Exit: normal, Duration: 12m 30s
- Log: OOMPAH-24__20260622T020455Z.jsonl
---
author: oompah
created: 2026-06-22 02:17
---
Agent completed without closing this issue (750s (4392647 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-06-22 02:17
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-06-22 02:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:20
---
UNDERSTANDING: Not a duplicate. OOMPAH-8 covers existing root/task smoke checks; OOMPAH-25, OOMPAH-31, and OOMPAH-42 cover broader wheel/bootstrap/post-release work. OOMPAH-24 specifically adds installed CLI smoke coverage for 'oompah project-bootstrap --help'. Plan: inspect current partial edits, add focused coverage, run relevant tests, commit/push, and close.
---
author: oompah
created: 2026-06-22 02:21
---
DISCOVERY: Relevant coverage is in tests/test_installed_cli_smoke.py: current editable install smoke checks always run, and isolated wheel smoke checks run when dist/*.whl exists. The CLI dispatch path is oompah/__main__.py -> oompah/project_bootstrap_cli.py. Existing release workflow/docs only covered oompah --help and oompah task --help; project-bootstrap help was the missing installed CLI smoke command.
---
author: oompah
created: 2026-06-22 02:22
---
IMPLEMENTATION: Added project-bootstrap help coverage in three places: the CLI release workflow now runs 'oompah project-bootstrap --help' after installing the built wheel; docs/cli-release.md lists that smoke command in the workflow and manual verification steps; tests now assert the workflow/docs include it and test both current-install and isolated-wheel 'oompah project-bootstrap --help' output for status/preview/apply subcommands.
---
author: oompah
created: 2026-06-22 02:28
---
Agent completed successfully in 616s (3872016 tokens)
---
author: oompah
created: 2026-06-22 02:28
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 43
- Tokens: 3.9M in / 16.5K out [3.9M total]
- Cost: $0.0000
- Exit: normal, Duration: 10m 16s
- Log: OOMPAH-24__20260622T021750Z.jsonl
---
author: oompah
created: 2026-06-22 02:28
---
Agent completed without closing this issue (616s (3872016 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-06-22 02:28
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-06-22 02:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:35
---
VERIFICATION: All 18 tests in test_cli_release_packaging.py and test_installed_cli_smoke.py pass (6 wheel-isolated tests skipped as expected without a built dist/*.whl).

Delivered:
- tests/test_installed_cli_smoke.py: two new tests covering 'oompah project-bootstrap --help' (current editable install + isolated venv)
- tests/test_cli_release_packaging.py: assertion that docs/cli-release.md mentions 'oompah project-bootstrap --help'  
- docs/cli-release.md: 'oompah project-bootstrap --help' added to the manual verification section

Not deliverable (token lacks workflow scope): adding the same smoke command to .github/workflows/cli-release.yml — filed as OOMPAH-47 for a human or workflow-scoped PAT to complete.
---
<!-- COMMENTS:END -->
