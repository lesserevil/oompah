---
id: OOMPAH-677
type: bug
status: Open
priority: 1
title: Prevent ownerless projects from deadlocking intake promotion
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T11:56:19.836343Z'
updated_at: '2026-08-01T11:56:21.902403Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live regression discovered on the NodeVirt managed project on 2026-08-01. The project was accepted with tracker_kind=oompah_md and intake Backlog tasks but had no status_actor_login, tracker_owner, or status_label_authorized_logins. Consequently every human Backlog to Open transition failed the project-owner gate even for the repository owner, leaving 21 tasks non-dispatchable until an operator manually patched project identity configuration. Implementation scope: validate or derive an owner-capable actor identity when creating and updating managed projects; cover GitLab and native Markdown tracker combinations where tracker_owner may be absent; expose the resolved authenticated actor and project owner configuration in an actionable dashboard rejection; do not weaken the owner-only dispatch boundary or trust client-supplied actor fields. Relevant areas: project create/update routes and models, actor mapping, transition gate, dashboard project forms/error handling, and project onboarding tests. Acceptance criteria: a newly configured dispatchable project cannot silently become ownerless; existing ownerless projects receive a visible health/configuration warning with a safe remediation; authenticated configured owners can promote Backlog to Open; non-owners remain rejected; regression tests reproduce the NodeVirt configuration and prove the repaired behavior.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

