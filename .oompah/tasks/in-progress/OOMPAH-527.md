---
id: OOMPAH-527
type: feature
status: In Progress
priority: 2
title: Derive GitLab webhook callback URL from the GitLab route
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T20:16:36.783511Z'
updated_at: '2026-07-28T20:17:20.820810Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5b18b096-2b14-4fad-a26a-0097a6c838c0
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
<!-- COMMENTS:END -->
