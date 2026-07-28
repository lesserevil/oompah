---
id: OOMPAH-495
type: chore
status: In Progress
priority: 2
title: Retire pre-implementation state-branch design tests
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels: []
assignee: null
created_at: '2026-07-28T13:53:30.405382Z'
updated_at: '2026-07-28T15:43:27.017454Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 6a57a446-e7d4-481a-b0e3-574f474d8ca1
oompah.work_branch: epic-OOMPAH-490
---
## Summary

Implementation scope

Remove `tests/test_state_branch_design.py`. It describes pre-implementation contracts and primarily tests constants or Git procedures authored inside the test instead of calling the shipped implementation. Before deletion, map each claimed contract to surviving implementation coverage in `tests/test_state_branch_project_config.py`, `tests/test_project_bootstrap_state_branch.py`, `tests/test_oompah_md_tracker_state_branch.py`, `tests/test_state_branch_e2e.py`, or `tests/test_checkpoint_coalescing.py`; add or strengthen a surviving test only if a real production contract is otherwise missing. Remove `TestXfailDesignContractNowPasses` from `test_state_branch_project_config.py` because its two checks duplicate earlier model-default tests in that file. Do not remove production bootstrap, migration, rollback, isolation, checkpoint, or malformed-task coverage.

Tests

Run the five surviving state-branch suites named above. Compare `--collect-only` output before and after and confirm no xfail message still says the state-branch feature is not implemented. Run `make test` after the Git-remote guard is present.

Acceptance criteria

The design-only module and duplicate post-xfail checks are gone, at least 22 collected cases are removed, every actual state-branch behavior remains covered through production APIs, and all surviving state-branch tests pass with local temporary remotes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 15:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 15:43
---
Understanding: This task asks to retire pre-implementation state-branch design tests by removing tests/test_state_branch_design.py and TestXfailDesignContractNowPasses from test_state_branch_project_config.py. Before any implementation, I am running duplicate screening to check whether this work is already covered by another task.
---
<!-- COMMENTS:END -->
