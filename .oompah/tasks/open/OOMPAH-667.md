---
id: OOMPAH-667
type: bug
status: Open
priority: 1
title: Keep Makefile virtualenv PATH from defeating canonical CLI cutover
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T21:32:57.017227Z'
updated_at: '2026-07-31T22:57:15.215950Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7599962d7e4882dd14f44d8ceea52fc73864838b17354027b56d93f81b9e7418
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 3a72a9ef-a71c-4663-a6e2-cd4fe7591a8b
  claim_owner: 83d630e6-ba64-48af-a521-3ffb6e2a4e3f
  claimed_at: '2026-07-31T22:57:08.018083+00:00'
  claim_expires_at: '2026-07-31T23:27:08.018083+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 3914909b-b264-483f-bb1b-1f08dd49c0a6
---
## Summary

Triggered by: OOMPAH-619

Production reproduction on merged main revision 16362384be835d1485d1121ce3c8329743391c79: running make sync-cli with the normal Makefile environment fails with "refusing CLI synchronization: command -v oompah resolves to .venv/bin/oompah; expected ~/.local/bin/oompah". Makefile globally prepends the project virtualenv to PATH so its internal Python and tools are available, but scripts/sync_canonical_cli.py correctly treats that same effective PATH as the operator command-resolution contract. The supported operational workaround make PATH="$PATH" sync-cli and make PATH="$PATH" restart succeeds, proving the selected revision and cutover logic are sound. Fix the Makefile and/or lifecycle scripts so internal virtualenv tool resolution is separated from validation of the caller/canonical CLI PATH; do not weaken detection of a genuinely shadowing noncanonical oompah executable. Add regression tests that invoke the real sync-cli and restart target environment with isolated HOME, UV tool directories, virtualenv, and canonical launcher; cover initial activation, already-current no-op, a true wrong-PATH refusal, install failure rollback, and successful server/CLI revision equality. Acceptance: unqualified make sync-cli and normal make restart work from a standard operator shell, command -v oompah still resolves to the canonical user launcher after cutover, CLI/server revisions match, and the focused lifecycle suites plus full project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 22:57
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 22:57
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
