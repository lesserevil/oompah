---
id: OOMPAH-667
type: bug
status: Backlog
priority: 1
title: Keep Makefile virtualenv PATH from defeating canonical CLI cutover
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T21:32:57.017227Z'
updated_at: '2026-07-31T21:32:57.017227Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-619

Production reproduction on merged main revision 16362384be835d1485d1121ce3c8329743391c79: running make sync-cli with the normal Makefile environment fails with "refusing CLI synchronization: command -v oompah resolves to .venv/bin/oompah; expected ~/.local/bin/oompah". Makefile globally prepends the project virtualenv to PATH so its internal Python and tools are available, but scripts/sync_canonical_cli.py correctly treats that same effective PATH as the operator command-resolution contract. The supported operational workaround make PATH="$PATH" sync-cli and make PATH="$PATH" restart succeeds, proving the selected revision and cutover logic are sound. Fix the Makefile and/or lifecycle scripts so internal virtualenv tool resolution is separated from validation of the caller/canonical CLI PATH; do not weaken detection of a genuinely shadowing noncanonical oompah executable. Add regression tests that invoke the real sync-cli and restart target environment with isolated HOME, UV tool directories, virtualenv, and canonical launcher; cover initial activation, already-current no-op, a true wrong-PATH refusal, install failure rollback, and successful server/CLI revision equality. Acceptance: unqualified make sync-cli and normal make restart work from a standard operator shell, command -v oompah still resolves to the canonical user launcher after cutover, CLI/server revisions match, and the focused lifecycle suites plus full project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

