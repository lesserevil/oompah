---
id: OOMPAH-453
type: bug
status: In Progress
priority: 1
title: Route webhook lifecycle by forge and stop gh forwarder churn for GitLab projects
parent: OOMPAH-451
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T12:34:51.844079Z'
updated_at: '2026-07-28T13:11:41.432748Z'
work_branch: epic-OOMPAH-451
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a5745b9f-3c07-4e58-b4c7-fd228b54fecb
oompah.work_branch: epic-OOMPAH-451
oompah.task_costs:
  total_input_tokens: 27
  total_output_tokens: 7039
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 27
      output_tokens: 7039
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 27
    output_tokens: 7039
    cost_usd: 0.0
    recorded_at: '2026-07-28T13:11:27.569442+00:00'
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
author: oompah
created: 2026-07-28 13:09
---
Understanding (Duplicate Investigator): Investigating whether OOMPAH-453 (route webhook lifecycle by forge, stop gh forwarder churn for GitLab projects) is a duplicate of any existing issue. Will search for related tasks around WebhookForwarder, GitLabHookManager, forge filtering, and webhook lifecycle before any implementation work.
---
author: oompah
created: 2026-07-28 13:10
---
Discovery: Duplicate screening found no confirmed duplicate for OOMPAH-453.

**Candidate tasks reviewed in full:**
- OOMPAH-341 (Merged): Implemented GitLabHookManager with OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL config. Cherry-picked onto epic-OOMPAH-451 as commit f6c4ef88d by the OOMPAH-452 Maintenance Engineer. Adds _is_gitlab_project() to GitLabHookManager but does NOT add forge filtering to WebhookForwarder._poll_and_restart.
- OOMPAH-342 (Merged): Wired GitLabHookManager into project lifecycle (reconcile/remove/dedup). Cherry-picked onto epic-OOMPAH-451 as commit 4c5420f7d. Again does NOT filter WebhookForwarder by forge.
- OOMPAH-452 (Done): Recovery epic child that cherry-picked commits from stranded epic-OOMPAH-318 branch onto current main (via epic-OOMPAH-451). PR #558 is open.

**Why OOMPAH-453 is distinct:**
Current oompah/webhooks.py line 1908: `projects = (self.project_store.list_all() if self.project_store else [])` — WebhookForwarder._poll_and_restart processes ALL projects with zero forge filtering. The recovered 341/342 commits only added GitLabHookManager with its own _is_gitlab_project() helper; neither patched WebhookForwarder to skip GitLab projects. The bug (gh webhook forward churn against GitLab repos) is still present on the current branch.
---
author: oompah
created: 2026-07-28 13:11
---
Focus handoff: duplicate_detector

1. **Outcome**: No duplicate confirmed. OOMPAH-453 is a unique, targeted bug fix.

2. **Evidence and key findings**:
   - Searched all .oompah/tasks/ directories and docs/plans for WebhookForwarder, GitLabHookManager, gh forwarder, forge filtering, forge_kind — no overlapping open/backlog tasks.
   - OOMPAH-341 (Merged) and OOMPAH-342 (Merged) covered GitLabHookManager implementation and lifecycle wiring; both were already cherry-picked onto epic-OOMPAH-451 branch (commits f6c4ef88d and 4c5420f7d) as part of OOMPAH-452.
   - Current branch already has GitLabHookManager, GitLabEventDedup, project lifecycle wiring (reconcile/remove), and hook health alerts.
   - **Root of the remaining bug**: WebhookForwarder._poll_and_restart (oompah/webhooks.py line 1906–1960) calls project_store.list_all() and processes every project, with no check for forge_kind. GitLab projects get a _ForwarderProcess created and `gh webhook forward` launched for them, producing HTTP 401s against api.github.com.
   - Neither 341 nor 342 modified _poll_and_restart to skip non-GitHub projects.

3. **Remaining work**:
   - Add forge filtering to WebhookForwarder._poll_and_restart: skip projects where forge_kind == 'gitlab' or 'gitlab' in repo_url (mirror the _is_gitlab_project() pattern in GitLabHookManager).
   - Add regression test with mixed GitHub+GitLab project_store fixture proving no gh subprocess launch and no api.github.com call for GitLab projects.
   - Tests for restart backoff, polling fallback, and configuration degradation/recovery as described in the issue.
   - Run make test to verify.
   - Key files: oompah/webhooks.py (WebhookForwarder._poll_and_restart ~line 1906, _launch ~line 2050), tests/test_webhooks.py.
   - All code is on branch epic-OOMPAH-451.

4. **Recommended next focus**: feature (targeted bug fix — add forge filter to WebhookForwarder, write regression tests).
---
author: oompah
created: 2026-07-28 13:11
---
Agent completed successfully in 159s (7066 tokens)
---
author: oompah
created: 2026-07-28 13:11
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 49, Tool calls: 36
- Tokens: 27 in / 7.0K out [7.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 39s
- Log: OOMPAH-453__20260728T130851Z.jsonl
---
author: oompah
created: 2026-07-28 13:11
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 13:11
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 13:11
---
Focus: Maintenance Engineer
---
<!-- COMMENTS:END -->
