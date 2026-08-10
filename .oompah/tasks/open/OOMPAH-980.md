---
id: OOMPAH-980
type: bug
status: Open
priority: 1
title: Reuse authoritative full branch gates in terminal audits
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T01:42:03.823626Z'
updated_at: '2026-08-10T01:42:33.008694Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by OOMPAH-979. Its exact branch head 7fc8bc8ea4a36c952a96349406a173c6b85ec94e had an authoritative full make test result recorded before review, but terminal audit authority treated the gate as incomplete and launched another full test run. Under the outer auditor validation environment, that redundant run also classified two ordinary native test lifecycles as opaque instead of full. Scope: reproduce the OOMPAH-979 branch-gate-to-terminal-audit path end to end; identify and fix the exact-head authority propagation or compatibility gap so a current compatible full gate is reused before any auditor process launch; add a native guard regression proving ordinary make test lifecycle telemetry stays full beneath an outer auditor guard without weakening hostile or leading-assignment fail-closed classification. Relevant context includes orchestrator exact-gate authority and audit launch policy, api_agent gate enforcement, validation_resource_lease, native validation guard and ACP lifecycle plumbing. Required tests: focused unit and integration regressions for compatible gate reuse, stale or incompatible rejection, no redundant auditor launch, nested native scope classification, and preserved opaque fail-closed cases. Acceptance: an OOMPAH-979-shaped exact-head full gate is reused rather than rerun; nested ordinary lifecycle scope remains full; no broad environment sanitization is introduced; focused tests and the complete project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 01:42
---
Claimed for direct-owner completion. Reproducing the exact OOMPAH-979 gate-authority and nested native lifecycle path on current main before changing production code.
---
<!-- COMMENTS:END -->
