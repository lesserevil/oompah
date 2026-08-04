---
id: OOMPAH-521
type: epic
status: In Validation
priority: 0
title: Add optional htpasswd authentication to the Oompah service
parent: null
children:
- OOMPAH-522
- OOMPAH-523
- OOMPAH-524
- OOMPAH-525
- OOMPAH-526
blocked_by: []
labels:
- security
- epic:rebasing
assignee: null
created_at: '2026-07-28T18:10:41.609070Z'
updated_at: '2026-08-04T21:51:44.729896Z'
work_branch: epic-OOMPAH-521
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/567
review_number: '567'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/567
oompah.review_number: '567'
oompah.work_branch: epic-OOMPAH-521
oompah.target_branch: main
oompah.agent_run_id: 1fe4b652-59d2-4d23-bd3b-a78ad519389e
oompah.task_costs:
  total_input_tokens: 64
  total_output_tokens: 12423
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 64
      output_tokens: 12423
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 64
    output_tokens: 12423
    cost_usd: 0.0
    recorded_at: '2026-07-28T21:21:41.634977+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-fb69a2491a3b
    project_id: proj-14849f1b
    task_id: OOMPAH-521
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 168332a1dae5a5f931cbf5f2dd6cfff21eb1353608aca2a641d1d5095ccaa723
    attempts:
    - version: 1
      attempt_id: attempt-2340da143f49
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 168332a1dae5a5f931cbf5f2dd6cfff21eb1353608aca2a641d1d5095ccaa723
      created_at: '2026-08-04T21:42:35.533088+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:42:35.533088+00:00'
      branch_key: epic-OOMPAH-521
      ended_at: '2026-08-04T21:51:43.462527+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T21:34:18.368853+00:00'
    updated_at: '2026-08-04T21:42:35.533088+00:00'
  - version: 1
    audit_id: audit-a62a16b4c5ff
    project_id: proj-14849f1b
    task_id: OOMPAH-521
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4064f1def222c29d08a7a51f584cdd185a90755d6d415a48ec48861efc74ed48
    attempts: []
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T21:43:59.803331+00:00'
  - version: 1
    audit_id: audit-01046260fd67
    project_id: proj-14849f1b
    task_id: OOMPAH-521
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4064f1def222c29d08a7a51f584cdd185a90755d6d415a48ec48861efc74ed48
    attempts: []
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T21:43:59.803331+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-2340da143f49
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 168332a1dae5a5f931cbf5f2dd6cfff21eb1353608aca2a641d1d5095ccaa723
    created_at: '2026-08-04T21:42:35.533088+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:42:35.533088+00:00'
    branch_key: epic-OOMPAH-521
    ended_at: '2026-08-04T21:51:43.462527+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
---
## Summary

### Goal

Add optional HTTP Basic authentication backed by an Apache-style htpasswd file so operators can safely expose Oompah through HTTPS. Authentication is disabled for backward compatibility when no htpasswd file is present. When the file is present, every human-facing and programmatic service surface must require valid credentials except narrowly documented machine-to-machine ingress and health endpoints.

### Configuration contract

- By default, discover `.htpasswd` beside the `.env` file selected at server startup.
- Allow `OOMPAH_HTPASSWD_FILE` in `.env` to select an absolute or environment-relative secret mount path.
- If the default file is absent and no override is configured, authentication remains disabled with current behavior.
- If an override is configured but missing, or a discovered file is unreadable, malformed, or contains no usable accounts, fail startup closed with an actionable error.
- Credential file changes take effect after a graceful service restart; no live-reload requirement is included in this epic.

### Security boundary

Require HTTP Basic credentials for dashboard pages and assets, REST/OpenAPI endpoints, WebSocket connections, MCP discovery and transport, and other interactive service routes. Keep only a minimal liveness endpoint and the GitHub/GitLab webhook receiver POST routes unauthenticated. Webhooks must retain their existing signature or token verification. Never log Authorization values or plaintext passwords. Document that Basic authentication must be deployed behind HTTPS.

### Child work

Children must implement credential loading and verification, ASGI HTTP/WebSocket enforcement and health separation, MCP authentication behavior, first-party CLI and service-control client support, and operator documentation and security regression coverage.

### Dependencies

Credential loading is the foundation. Server enforcement depends on it. MCP and first-party client integration depend on server enforcement and may proceed in parallel. Documentation and final integration verification depend on all implementation children.

### Test requirements

Every child must add focused tests. The completed epic must pass make test and include end-to-end tests for auth disabled, valid credentials, invalid or absent credentials, malformed configuration, protected HTTP and WebSocket surfaces, protected MCP access, unauthenticated signed webhooks, and unauthenticated minimal health checks.

### Acceptance criteria

1. Starting Oompah with no discovered or configured htpasswd file preserves existing unauthenticated behavior.
2. Starting with a valid htpasswd file makes all in-scope HTTP, WebSocket, OpenAPI, and MCP surfaces require valid Basic credentials.
3. Invalid credentials return 401 with an appropriate WWW-Authenticate challenge and do not disclose why verification failed.
4. Missing or invalid explicitly configured credential files fail closed and explain remediation without exposing secrets.
5. GitHub and GitLab webhook delivery continues to work without Basic credentials and still requires the existing forge-specific authentication.
6. A minimal non-sensitive health endpoint remains suitable for process supervision without credentials.
7. Oompah CLIs and Makefile lifecycle operations can authenticate without putting passwords in URLs, logs, or command output.
8. Operator documentation covers setup, password creation and rotation, HTTPS, exclusions, client configuration, disablement, and recovery.
9. The full make test gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:17
---
Branch quality gate passed for `4a15c3ecb298cf0e4812146b2bba3d45877c2527` using `make test` in 69.0s. Review creation may proceed.
---
author: oompah
created: 2026-07-28 21:17
---
YOLO: Merge conflict detected on MR #567. Rebase `epic-OOMPAH-521` onto main and resolve conflicts.
---
author: oompah
created: 2026-07-28 21:17
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 21:17
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-07-28 21:17
---
Understanding: Task is to rebase epic-OOMPAH-521 (10 commits, OOMPAH-522/523/524/525/526) onto origin/main. Merge base is at 0237f7730 (Merge pull request #564). Main is 4 commits ahead (OOMPAH-457, OOMPAH-527). Will fetch, rebase, resolve conflicts, then run focused auth tests.
---
author: oompah
created: 2026-07-28 21:21
---
Rebase complete. Rebased epic-OOMPAH-521 (10 commits) onto origin/main.

## Conflicts resolved
- **.env.example**: OOMPAH-527 rewrote OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL doc block to describe route-derived defaults; OOMPAH-526 added a note about independence from OOMPAH_HTPASSWD_FILE. Kept OOMPAH-527's newer text and appended the HTPASSWD independence note.
- **oompah/bootstrap.py**: main added \`terminal_transition_coordinator\` field to Services; OOMPAH-526 added \`http_credentials\` field. Kept both fields in the dataclass.
- **tests/test_granian_bootstrap.py**: main added mock_config.gitlab_webhook_public_url = None; OOMPAH-526 added mock_config.htpasswd_file = None. Kept both mock assignments.

## Additional cleanup
- Pre-existing uncommitted uv.lock update (bcrypt/passlib entries for OOMPAH-522) was folded into 59f266727 via git commit --fixup + autosquash. Without this, uv sync --frozen fails on the branch.

## Verification
- \`uv sync --frozen --extra server\` succeeds.
- Focused suites: 597 tests pass (test_http_auth, test_config, test_granian_bootstrap, test_server_auth, test_client_auth, test_lifespan_abort, test_docs_authentication_contract, test_mcp_gateway, test_mcp_exposure_policy).
- Neighboring suites: 179 tests pass (test_task_cli, test_admin_cli, test_config_agent_profile_store, test_gitlab_bootstrap_readiness).

Branch force-pushed to origin/epic-OOMPAH-521 (head 0f3a7bfd1). All 10 original commits preserved; no commits dropped or squashed except the uv.lock fixup.
---
author: oompah
created: 2026-07-28 21:21
---
Merge conflict resolution complete. Rebased epic-OOMPAH-521 onto origin/main (all 10 OOMPAH-522/523/524/525/526 commits preserved). Resolved conflicts in .env.example, oompah/bootstrap.py, and tests/test_granian_bootstrap.py by keeping both sides' additions. Folded uncommitted uv.lock (bcrypt/passlib deps for OOMPAH-522) into commit 59f266727 via autosquash. Focused test suites pass: 597 auth/config/bootstrap/mcp tests + 179 CLI/lifecycle tests. Branch force-pushed to origin (head 0f3a7bfd1).
---
author: oompah
created: 2026-07-28 21:21
---
Agent completed successfully in 248s (12487 tokens)
---
author: oompah
created: 2026-07-28 21:21
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Claude/opus]
- Turns: 83, Tool calls: 58
- Tokens: 64 in / 12.4K out [12.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 8s
- Log: OOMPAH-521__20260728T211737Z.jsonl
---
author: oompah
created: 2026-07-28 21:22
---
Branch quality gate passed for `0f3a7bfd1c75ee161a493583a60fc2c1a42d18b5` using `make test` in 69.5s. Review creation may proceed.
---
author: oompah
created: 2026-07-28 21:30
---
YOLO: merged PR #567.
---
author: oompah
created: 2026-08-04 21:34
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
