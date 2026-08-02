---
id: OOMPAH-707
type: task
status: Open
priority: null
title: Preserve explicit owner work from orphaned-In-Progress reset
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T22:19:11.796639Z'
updated_at: '2026-08-02T22:37:59.967233Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-701\n\nProduction evidence on 2026-08-02: the authenticated project owner placed human-only OOMPAH-701 In Progress for direct implementation with an explicit handoff comment and active task worktree, but _reset_orphaned_in_progress changed it back to Open twice because no scheduler RunningEntry was attached. This makes direct owner work look idle and can expose it to conflicting lifecycle automation.\n\nImplementation scope:\n- Represent a durable direct-owner claim/lease, or another explicit ownership fence, that distinguishes intentional owner work from a genuinely orphaned scheduler assignment.\n- Make _reset_orphaned_in_progress preserve a live owner claim while retaining recovery of truly abandoned tasks.\n- Expose the ownership source and staleness/expiry evidence in API/UI state.\n- Define bounded expiry/release behavior so an abandoned owner claim cannot strand work indefinitely.\n\nRelevant code: oompah/orchestrator.py _reset_orphaned_in_progress and watchdog maintenance; task status/assignment APIs; native Markdown tracker metadata; dashboard task/agent ownership state.\n\nRequired tests:\n- Direct owner claim plus human-only and In Progress survives repeated orphan watchdog scans.\n- Expired/explicitly released owner claim is safely reset through the existing recovery path.\n- Scheduler-owned orphan behavior remains unchanged.\n- Owner claim versus watchdog scan is serialized so neither transition can overwrite a newer decision.\n\nAcceptance criteria:\n- Intentional direct owner work remains visibly In Progress without a scheduler agent.\n- Genuine orphan recovery stays bounded and automatic.\n- Focused race tests and make test/check-secrets pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 22:37
---
Promoted to Open after confirming the live watchdog reset direct project-owner work twice. The description contains the production evidence, implementation scope, required race tests, and bounded owner-claim acceptance criteria; Oompah may dispatch it normally while the directly owned OOMPAH-701 repair proceeds.
---
<!-- COMMENTS:END -->
