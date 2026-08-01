---
id: OOMPAH-675
type: bug
status: Open
priority: 1
title: Keep the parallel pytest gate stable when workers terminate
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T04:59:55.163807Z'
updated_at: '2026-08-01T05:10:57.075570Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5ab5cde2ab072b5c4f07af63d1f20e0931acb6036cfa517d764ef6c88708cd73
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 98e4aa8f-1cc1-420a-9c72-bc544e284c5d
  claim_owner: cd8a4634-d8cd-489c-950d-630a9fe1bdff
  claimed_at: '2026-08-01T05:10:51.505900+00:00'
  claim_expires_at: '2026-08-01T05:40:51.505900+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 70bd1f7f-beff-4986-9b0d-8fddcaa2b827
---
## Summary

Discovered while validating OOMPAH-674 on 2026-08-01. Two consecutive make test runs with the configured four xdist workers aborted after workers reported node down: Not properly terminated; xdist created replacement workers and LoadGroupScheduling then crashed with KeyError for WorkerController gw6. Runs stopped near 47 percent with roughly 6,956 tests passed, so the controller did not preserve actionable identities for the original failures. Focused one-worker selections pass. Implementation scope: reproduce and identify why bounded tests terminate xdist workers, ensure lifecycle or process-group tests cannot kill their pytest worker, and make the gate surface original test failures without scheduler-internal replacement crashes. Relevant areas: Makefile test target, scripts/run-tests.sh, pytest timeout and xdist configuration, process lifecycle tests. Acceptance criteria: repeated configured four-worker gates complete without lost workers or xdist internal errors; intentional timeouts report the responsible test; isolation guarantees remain intact; regression coverage exercises worker failure and replacement behavior where practical.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 05:10
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 05:10
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
