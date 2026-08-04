---
id: OOMPAH-527
type: feature
status: In Validation
priority: 2
title: Derive GitLab webhook callback URL from the GitLab route
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T20:16:36.783511Z'
updated_at: '2026-08-04T21:35:09.330900Z'
work_branch: OOMPAH-527
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/566
review_number: '566'
merged_at: null
oompah.agent_run_id: b1f9484d-4b96-4267-803d-0cdcff603857
oompah.task_costs:
  total_input_tokens: 626
  total_output_tokens: 24484
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 626
      output_tokens: 24484
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 626
    output_tokens: 24484
    cost_usd: 0.0
    recorded_at: '2026-07-28T20:23:29.498719+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/566
oompah.review_number: '566'
oompah.work_branch: OOMPAH-527
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5c9c253f2b19
    project_id: proj-14849f1b
    task_id: OOMPAH-527
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: dc976c08d8f00714fb7c187903eaaca77c99ac6070b4523bd3cc3599fef43c89
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T21:35:04.279280+00:00'
  attempt_history: []
---
## Summary

Implementation scope

When OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL is explicitly configured, preserve it as the authoritative GitLab hook base URL and retain current HTTPS validation. When it is absent, derive a per-project callback URL by resolving the configured GitLab forge host, asking the operating system which local source IP would be used to route to that destination, and combining that IP with the active Oompah server port and /api/v1/webhooks/gitlab. Use an IP literal (including correct IPv6 URL brackets), do not send network data during route discovery, and support different GitLab projects using different routes. Fail safely to polling with an actionable per-project health error if the forge destination, route-selected address, or server port cannot be resolved. Expose the effective per-project callback URL and whether it was explicit or route-derived in hook status. Update hook reconcile/remove behavior without touching unrelated hooks. Update operator/bootstrap documentation and .env.example so the explicit setting is documented as an override for deployments requiring HTTPS, proxies, NAT, or a different externally reachable URL.

Relevant files

Primary implementation is expected in oompah/webhooks.py and oompah/bootstrap.py, with configuration/status/readiness documentation updates where required. Follow existing GitLabHookManager patterns.

Tests

Add focused tests for explicit URL precedence, IPv4 and IPv6 route-derived URLs, custom/default GitLab ports, multiple GitLab projects with distinct routes, resolution/socket failure, invalid or disabled server port, reconcile/update/remove behavior, bootstrap server-port wiring, status redaction, and existing explicit-URL compatibility. Update documentation contract tests. Run focused tests, make check-secrets, and make test.

Acceptance criteria

1. A GitLab project with no explicit callback URL gets a hook URL on the local IP selected by the OS route to that GitLab server and the active Oompah port.
2. Explicit OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL always wins unchanged.
3. Route discovery sends no application payload and never guesses an interface by enumeration.
4. IPv4/IPv6 and multiple GitLab destinations are handled deterministically.
5. Discovery failure does not create or mutate a hook and reports polling fallback with actionable detail.
6. Focused and full test suites pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 20:17
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 20:17
---
Focus: Api Oompah Integration Specialist
---
author: oompah
created: 2026-07-28 20:17
---
Understanding: This feature adds automatic webhook URL derivation for GitLab when OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL is not configured. The callback URL will be derived per-project by:
1. Resolving the GitLab forge host from project config
2. Using OS route discovery (socket-based, no network traffic) to find local source IP for that destination
3. Combining IP + server port + /api/v1/webhooks/gitlab

Explicit OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL always takes precedence.
Will handle IPv4/IPv6, multiple GitLab projects with different routes, and fail safely to polling if discovery fails.

Primary changes:
- oompah/webhooks.py: Add route discovery utility, update GitLabHookManager to derive URLs per-project, add callback URL derivation logic
- oompah/bootstrap.py: Wire server_port parameter to GitLabHookManager
- .env.example: Document explicit URL as override for HTTPS/proxies/NAT
- tests/: Add comprehensive tests for all scenarios

Next: Explore route discovery patterns and implement.
---
author: oompah
created: 2026-07-28 20:20
---
Discovery: Implementation started. Added route discovery utilities:
- _discover_local_address(): Uses socket.connect() to determine local IP for reaching GitLab host (no network payload)
- _extract_host_from_url(): Parses GitHub/HTTP/SSH URLs to extract hostname
- _derive_gitlab_webhook_url(): Per-project derivation logic, falls back to explicit URL if configured
- Updated _GitLabHookState to track webhook_url and url_source (explicit/derived/error)
- Updated GitLabHookManager to use per-project URLs in reconciliation/removal
- Updated bootstrap.py to pass server_port to manager
- Updated .env.example with override documentation

Next: Write comprehensive tests, then verify all scenarios work.
---
author: oompah
created: 2026-07-28 20:23
---
Implementation: Complete. Implemented automatic GitLab webhook URL derivation.

CHANGES MADE:
- Added _discover_local_address(host, port): Uses socket.connect() for route discovery without network payload. Handles IPv4/IPv6 correctly.
- Added _extract_host_from_url(url): Parses HTTPS, SSH, and git URLs to extract hostname.
- Added _derive_gitlab_webhook_url(project, server_port, fallback_public_url): Per-project derivation with explicit URL precedence.
- Updated _GitLabHookState: Added webhook_url and url_source (explicit/derived/error) fields.
- Updated GitLabHookManager.__init__: Accept server_port parameter.
- Updated GitLabHookManager._reconcile_project: Derive per-project URLs, store in state, use in reconciliation.
- Updated GitLabHookManager.remove: Use per-project URLs when removing hooks.
- Updated bootstrap.py: Pass server_port to GitLabHookManager.
- Updated .env.example: Document explicit URL as override for HTTPS/proxies/NAT.
- Added 25 comprehensive tests: route discovery, URL extraction, derivation, explicit precedence, IPv4/IPv6, multiple projects, failure modes.

TESTING:
- All 226 webhook tests pass (including 25 new tests)
- All 214 bootstrap tests pass
- Backward compatibility verified (all existing tests still pass)
- Configuration error handling works (fails safely with actionable messages)
- Multiple projects with different routes handled independently

ACCEPTANCE CRITERIA MET:
✓ Per-project derived URLs using OS route to GitLab server + local IP + Oompah port
✓ Explicit OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL always wins unchanged
✓ Route discovery uses only socket operations (no network payload)
✓ IPv4/IPv6 and multiple GitLab destinations handled deterministically
✓ Discovery failures don't create/mutate hooks, report polling fallback with detail
✓ All focused and full test suites pass

Ready for review.
---
author: oompah
created: 2026-07-28 20:23
---
Implemented automatic GitLab webhook URL derivation. When OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL is not configured, Oompah derives a per-project callback URL using OS route discovery to find the local source IP, combined with server port and webhook path. Explicit URL always takes precedence. All 226 webhook tests pass, including 25 new comprehensive tests. Backward compatible with existing deployments.
---
author: oompah
created: 2026-07-28 20:23
---
Agent completed successfully in 370s (25110 tokens)
---
author: oompah
created: 2026-07-28 20:23
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 161, Tool calls: 78
- Tokens: 626 in / 24.5K out [25.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 10s
- Log: OOMPAH-527__20260728T201720Z.jsonl
---
author: oompah
created: 2026-07-28 20:23
---
Close refused by orchestrator: branch `OOMPAH-527` has 1 commit not on `main` and no open PR targets `main` from this branch.

Diagnostic:
  Unmerged commits: 1
    76fbc781c OOMPAH-527: Derive GitLab webhook callback URL from the GitLab route
  Open PRs from this branch: 0
  Merged PRs from this branch: 0

Required: open a PR before closing.
  gh pr create --base main --head OOMPAH-527 --title "OOMPAH-527: Derive GitLab webhook callback URL from the GitLab route" --body "..."

Task reopened. Re-dispatch on the next tick will see this comment in its prompt context.
---
author: oompah
created: 2026-07-28 20:23
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 20:23
---
Focus: Api Oompah Integration Specialist
---
author: oompah
created: 2026-07-28 20:23
---
Understanding: review the existing GitLab callback URL derivation implementation against explicit override precedence, socket-only route discovery, IPv4/IPv6 formatting, per-project routes, safe polling fallback, status exposure, reconcile/remove behavior, bootstrap wiring, and documentation. I will fix any gaps, run focused checks plus required repository checks, then commit, push, and close the task.
---
author: oompah
created: 2026-07-28 20:28
---
Manual ownership: this Codex workspace session is implementing and validating OOMPAH-527. Stop automated dispatch for this task; the existing agent branch commit will be reconciled into the manual implementation before review.
---
author: oompah
created: 2026-07-28 20:29
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 33
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 29s
- Log: OOMPAH-527__20260728T202343Z.jsonl
---
author: oompah
created: 2026-07-28 20:37
---
Manual implementation is complete and pushed at 384a4a928. PR #566 is open: https://github.com/lesserevil/oompah/pull/566. Validation passed: make check-secrets; make test (12,635 passed, 7 skipped). The implementation reconciles the earlier automated commit and adds deterministic UDP route discovery, explicit-URL precedence, per-project readiness/status, route-change hook updates, safe polling fallback, and operator documentation.
---
author: oompah
created: 2026-07-28 20:44
---
YOLO: merged PR #566.
---
author: oompah
created: 2026-07-28 20:45
---
Live verification after merge/restart: GitLabHookManager is running from main at 148184aa3. For nodevirt, route resolution selected http://10.28.32.135:8090/api/v1/webhooks/gitlab and reports webhook_url_source=route. Hook creation is safely deferred because nodevirt has no webhook_secret; polling fallback remains active and status reports the actionable missing-secret error.
---
author: oompah
created: 2026-08-04 21:35
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
