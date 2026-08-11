---
id: OOMPAH-1128
type: bug
status: Backlog
priority: 1
title: Deduplicate auto-filed retry failures using stable incident identities
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T22:38:40.818634Z'
updated_at: '2026-08-11T22:38:40.818634Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: incident-20260811-stable-error-watcher-identities
  request_fingerprint: cd782db30139e2c1d3347519044c9aa72728bd131593f9018545163028d44543
---
## Summary

Triggered by: OOMPAH-1099

One checkpoint incident generated 25 Backlog tasks because error-watcher fingerprints changed with the volatile push_failures=N counter. Existing duplicate suppression therefore treated every retry as a new incident. Error identities must be stable without collapsing genuinely independent failures.

Implementation scope:
- Update oompah/error_watcher.py fingerprinting and the checkpoint_queue and terminal_transition_coordinator call sites that submit errors.
- Prefer explicit, stable error-class/incident keys from callers; normalize volatile counters, timestamps, retry numbers, and similar changing telemetry when deriving a fallback fingerprint.
- Keep useful changing telemetry in comments or occurrence metadata while retaining one canonical task.
- Define whether task identifiers such as TRICKLE-129 are incident identity or context at each caller so failures for distinct tasks are not accidentally merged.

Required tests:
- Feed otherwise identical checkpoint failures with push_failures values 1 through 25 and assert one task is created and subsequent occurrences update it.
- Verify debounce, max-delay, and terminal-triggered retries for the same underlying push outage consolidate appropriately.
- Verify semantically distinct projects, backends, and per-task terminal-transition failures remain separate where required.

Acceptance criteria:
- A persistent retrying backend fault creates one actionable task rather than an unbounded task stream.
- The canonical task records recurrence/current evidence.
- Existing cross-restart duplicate suppression remains effective and distinct incidents remain distinguishable.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

