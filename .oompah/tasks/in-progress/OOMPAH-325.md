---
id: OOMPAH-325
type: task
status: In Progress
priority: 1
title: Add GitLab project-hook lifecycle and webhook event parity
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-319
labels:
- focus-complete:duplicate_detector
- needs:feature
assignee: null
created_at: '2026-07-21T20:34:27.176966Z'
updated_at: '2026-07-22T00:18:34.525863Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 6b85d10d-5f23-4596-91b2-bc6362b142e5
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, Webhooks, UI, bootstrap, and operations.

Implement GitLab Project Hook management separate from the gh-webhook forwarder. Require/configure OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL, create/reconcile/remove GitLab hooks with a per-project secret, and record hook health. Extend webhook parsing and server handling for Push Hook, Merge Request Hook, Issue Hook, Note Hook, Pipeline Hook, Job Hook, and label-relevant events. Normalize all into WebhookEvent/EventBus and retain polling fallback.

Do not manage reverse proxies or tunnels; the operator provides public HTTPS reachability.

Tests:
- Hook API create/update/delete/reconciliation and redacted error fixtures.
- Token validation, project matching, event normalization, delivery deduplication, and health degradation/recovery.
- Existing gh webhook forwarder tests remain unchanged.

Acceptance criteria:
- A GitLab project receives authenticated event-driven MR, issue, and pipeline updates, with clear polling-fallback alerts on failure.
- No webhook secret or token appears in logs/API responses.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 00:16
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 00:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 00:17
---
Understanding: Investigating OOMPAH-325 for duplicates before any implementation. This task requests GitLab project-hook lifecycle management (create/reconcile/remove hooks with per-project secrets), webhook event parsing (Push, MR, Issue, Note, Pipeline, Job hooks), normalization into WebhookEvent/EventBus, and polling fallback. Plan reference: plans/gitlab-forge-parity.md. Searching for any existing tasks covering the same ground.
---
author: oompah
created: 2026-07-22 00:18
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed. OOMPAH-325 is a distinct, unique child of OOMPAH-318 (GitLab forge parity epic). No existing task in any state (backlog/done/archived/merged/needs-ci-fix/needs-rebase) covers GitLab project-hook lifecycle management, OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL configuration, push/MR/issue/note/pipeline/job hook normalization, or polling-fallback logic.

2. Evidence:
   - Searched .oompah/tasks/ for: gitlab, webhook, project-hook, hook-lifecycle, EventBus, WebhookEvent, GITLAB_WEBHOOK_PUBLIC_URL, push hook, merge request hook, pipeline hook — zero hits
   - Reviewed OOMPAH-318 (parent epic): sibling tasks cover forge config (319), SCM contract (320), MR provider (321), pipeline CI (322), Issues tracker (323), review/YOLO integration (326), intake bridge (324), UI/API (327), bootstrap docs (328), cross-forge e2e (329) — none covers webhook hook lifecycle
   - OOMPAH-319 (blocker, Done): only implements forge_kind/forge_base_url model fields
   - Plan reference plans/gitlab-forge-parity.md section 'Webhooks, UI, bootstrap, and operations' describes exactly OOMPAH-325's scope as a separate numbered item
   - Git history contains no merged implementation of GitLab hook management

3. Remaining work: Full implementation per description — GitLabHookManager class, OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL config, create/reconcile/remove hooks with per-project secrets, webhook endpoint parsing (Push, MR, Issue, Note, Pipeline, Job hooks), WebhookEvent normalization, EventBus wiring, hook health tracking, polling fallback, and comprehensive tests. Blocker OOMPAH-319 is Done.

4. Recommended next focus: feature (backend implementation of GitLab hook lifecycle and webhook event parity)
---
<!-- COMMENTS:END -->
