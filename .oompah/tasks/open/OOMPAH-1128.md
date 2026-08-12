---
id: OOMPAH-1128
type: bug
status: Open
priority: 1
title: Deduplicate auto-filed retry failures using stable incident identities
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-11T22:38:40.818634Z'
updated_at: '2026-08-12T19:58:12.640599Z'
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
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 160debb635c1fc4cb7d03f53a751939dedbd715a745f3137570d88a780442d72
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 43eb87265afb7682ebacbbef09be8a5c20cf6aaeea1da7055c2f44247733e9cc:11841
  claim_owner: 02fd371b-4f1d-4e9b-a422-f3effd90464e
  claimed_at: '2026-08-12T15:59:56.968581+00:00'
  claim_expires_at: '2026-08-12T16:29:56.968581+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: b009276c-a134-45fd-933d-60bf78df08a8
oompah.work_contributors:
  runs:
  - run_id: 5a2bd3fd887d4f75bb2b8f76deb5c86d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1128
    source_sha: null
    completed_at: ''
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-a050382e3c32
    project_id: proj-14849f1b
    task_id: OOMPAH-1128
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: aebe42575c8bb288397e30f621e4904c79316073e316ed3f11c31098f2aee58b
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Direct-owner completion verified in merged PR #836 at a6a983171: stable
      incident identities and retry coalescing are implemented with regression coverage;
      the exact merge passed the full Python 3.11/3.12/3.13 CI matrix.'
    created_at: '2026-08-12T19:58:09.722261+00:00'
    selected_ref: origin/main
    selected_sha: 00db66b58afc1dfbb67572226213a8da8fd22ec4
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 01:38
---
Direct operator ownership is active on branch OOMPAH-1130. The workflow-authorized Open → In Progress transition is currently unavailable because OOMPAH-1130 prevents publication of the required generation; this comment and branch are the durable ownership handoff until that blocker is repaired.
---
author: oompah
created: 2026-08-12 16:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
