---
id: OOMPAH-453
type: bug
status: In Progress
priority: 1
title: Route webhook lifecycle by forge and stop gh forwarder churn for GitLab projects
parent: OOMPAH-451
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T12:34:51.844079Z'
updated_at: '2026-07-28T13:08:51.507060Z'
work_branch: epic-OOMPAH-451
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a3cc3249-8cb2-40bf-a84e-3aaa903cb156
oompah.work_branch: epic-OOMPAH-451
---
## Summary

Problem: adding nodevirt as forge_kind=gitlab causes WebhookForwarder to launch gh webhook forward against GitHub shedwards/nodevirt every five seconds, producing HTTP 401 errors and subprocess/log churn. Current main never filters WebhookForwarder projects by forge and lacks the GitLabHookManager work from OOMPAH-341 and OOMPAH-342, although those tasks are marked Merged.

Implementation scope: make the gh forwarder manage GitHub projects only; selectively reconcile GitLabHookManager and lifecycle wiring from commits 4302b74e8 and 62cde900b onto current main; reconcile hooks only when public HTTPS URL, project secret, and token are configured; expose forge-specific hook health and a bounded polling fallback; avoid retry loops for expected missing webhook configuration. Relevant files include oompah/webhooks.py, oompah/bootstrap.py, oompah/server.py, oompah/config.py, .env.example, and lifecycle tests.

Tests: regression fixture with mixed GitHub and GitLab projects proving no gh subprocess or api.github.com request is made for GitLab; hook create/update/delete, redaction, configuration degradation/recovery, polling fallback, and restart backoff tests; run make test.

Acceptance criteria: nodevirt causes no GitHub 401 or child-process churn; GitHub forwarding remains intact; configured GitLab hooks reconcile through the GitLab API; unconfigured hooks surface one actionable health state while polling remains available.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 13:08
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 13:08
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
