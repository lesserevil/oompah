---
id: OOMPAH-522
type: feature
status: In Progress
priority: 1
title: Load and verify optional htpasswd credentials safely
parent: OOMPAH-521
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T18:11:34.097786Z'
updated_at: '2026-07-28T18:36:07.654080Z'
work_branch: epic-OOMPAH-521
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9b5e2f99-f068-44bb-b903-34a99a2984d8
oompah.work_branch: epic-OOMPAH-521
oompah.task_costs:
  total_input_tokens: 259304
  total_output_tokens: 6461
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 259304
      output_tokens: 6461
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 218
    output_tokens: 4726
    cost_usd: 0.0
    recorded_at: '2026-07-28T18:34:19.861878+00:00'
  - profile: default
    model: haiku
    input_tokens: 259086
    output_tokens: 1735
    cost_usd: 0.0
    recorded_at: '2026-07-28T18:35:20.855417+00:00'
---
## Summary

### Objective

Implement the configuration and credential-verification foundation for optional Oompah HTTP Basic authentication. This task does not apply authentication to routes; it provides a tested component and startup contract for the server enforcement child.

### Implementation scope

- Add a focused authentication module, such as `oompah/http_auth.py`, that parses an Apache-style htpasswd file and verifies a supplied username and password.
- Add `OOMPAH_HTPASSWD_FILE` to `ServiceConfig`, `.env` loading, startup wiring, and `.env.example`.
- Preserve the absolute path of the selected `--env-file` during startup. With no override, discover `.htpasswd` in that file directory. Resolve a relative override against the same directory; accept an absolute override for container secret mounts.
- Define explicit states: default file absent means disabled; valid file means enabled; explicitly configured missing file means fatal; present but unreadable, malformed, or empty file means fatal.
- Load credentials during startup and require a graceful restart after changes. Do not silently disable authentication if a previously selected file cannot be loaded.
- Use a maintained password-verification implementation rather than inventing password hashing. Keep any new dependency in the server and dev extras so the standalone task CLI remains lightweight.
- Support and test at least bcrypt and APR1 hashes emitted by common Apache `htpasswd` commands. Reject plaintext password records. Document any additional supported formats in the module and operator documentation child.
- Use constant-time verification where the selected library does not already guarantee it. Return the same verification failure for unknown users and wrong passwords. Never log usernames with passwords, password values, hashes, or Authorization headers.
- Ensure `.htpasswd` and documented local credential-file variants are ignored by git without weakening existing secret scanning.

### Relevant files

`oompah/config.py`, `oompah/__main__.py`, `oompah/bootstrap.py`, `pyproject.toml`, `uv.lock`, `.env.example`, `.gitignore`, a new focused auth module, and tests following existing config/startup patterns.

### Dependencies

None. This is the foundation for the other epic children.

### Test requirements

Add unit tests for disabled discovery, default discovery beside a non-default env file, relative and absolute overrides, valid bcrypt and APR1 verification, unknown user, wrong password, malformed lines, unsupported or plaintext hashes, unreadable files, empty files, and explicit missing paths. Add startup/config tests proving fatal cases fail before the service begins listening. Do not use real operator credentials in fixtures.

### Acceptance criteria

1. No default file and no override yields a clear disabled auth configuration.
2. A valid `.htpasswd` beside the selected env file enables a verifier at startup.
3. Relative and absolute `OOMPAH_HTPASSWD_FILE` values resolve deterministically.
4. Valid bcrypt and APR1 fixtures authenticate; invalid credentials fail without revealing which field was wrong.
5. Explicit missing, unreadable, malformed, empty, plaintext, and unsupported credential files fail closed with actionable secret-free errors.
6. Server-only dependencies do not expand the standalone CLI installation.
7. Focused tests pass through the project test tooling.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:32
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 18:34
---
Duplicate screening complete: No duplicate found.

Investigation scope:
- Searched .oompah/tasks for htpasswd, http*auth, basic*auth, credential patterns: no matches
- Reviewed all open tasks: only OOMPAH-281 (unrelated - CI/container runner)
- Reviewed all backlog tasks: only OOMPAH-282 (unrelated - state migration bug)
- Checked merged/archived tasks for auth-related work: only OOMPAH-6 (GitHub API intake auth, not htpasswd)
- Verified codebase: no OOMPAH_HTPASSWD_FILE config, no http_auth module, no htpasswd implementation

Confirmed context:
- OOMPAH-521 is the parent epic for HTTP Basic auth feature
- OOMPAH-522-526 are distinct child tasks (credential loading → enforcement → MCP integration → CLI support → documentation)
- This is new work with no prior implementation

This is a fresh feature task with no duplicate. Ready for implementation specialist.
---
author: oompah
created: 2026-07-28 18:34
---
Agent completed successfully in 99s (4944 tokens)
---
author: oompah
created: 2026-07-28 18:34
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 57, Tool calls: 27
- Tokens: 218 in / 4.7K out [4.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 39s
- Log: OOMPAH-522__20260728T183250Z.jsonl
---
author: oompah
created: 2026-07-28 18:34
---
Focus handoff required before leaving `duplicate_detector`. Add a comment headed `Focus handoff: duplicate_detector` with outcome, evidence, remaining work, and next focus.
---
author: oompah
created: 2026-07-28 18:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:34
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 18:35
---
Focus handoff: duplicate_detector\n\nOutcome: No duplicate confirmed; OOMPAH-522 is distinct new feature work.\n\nEvidence: Searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for htpasswd/HTTP Basic/password/auth patterns. Reviewed OOMPAH-6 in full; it addresses GitHub API intake credentials only (TrackerAuthError and dashboard alerts), not Apache htpasswd loading or HTTP Basic authentication. OOMPAH-281 and OOMPAH-282 are unrelated. Repository search found no OOMPAH_HTPASSWD_FILE or existing htpasswd module.\n\nRemaining work/risk: Implement the described config, startup loading, bcrypt/APR1 verification, fail-closed errors, dependency boundary, gitignore updates, and focused tests. Preserve secret-free diagnostics and verify failures occur before listening.\n\nRecommended next focus: feature.
---
author: oompah
created: 2026-07-28 18:35
---
Agent completed successfully in 51s (260821 tokens)
---
author: oompah
created: 2026-07-28 18:35
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 7
- Tokens: 259.1K in / 1.7K out [260.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 51s
- Log: OOMPAH-522__20260728T183433Z.jsonl
---
author: oompah
created: 2026-07-28 18:35
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 18:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:35
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-28 18:36
---
Security Audit: Understanding phase - reviewing htpasswd credential loading implementation.

Security focus areas identified for review:
1. **Authentication Module Design** - verify secure password verification implementation
2. **Configuration & Startup** - ensure fatal failures occur before service listening
3. **File Handling** - validate safe path resolution and permission checks
4. **Data Exposure** - prevent credential leaks in logs/errors/diagnostics
5. **Dependency Management** - ensure server-only deps don't bloat task CLI
6. **OWASP Compliance** - check for Top 10 vulnerabilities (A2:Broken Auth, A3:Injection, A4:Insecure Design, A6:Vulnerable Deps)

Planned audit approach:
- Review implementation for secure password verification (bcrypt/APR1 support, constant-time checks)
- Validate error handling doesn't expose secrets or usernames
- Verify config loading fails safely on missing/unreadable/invalid files
- Check gitignore patterns prevent credential exposure
- Audit startup sequence for fail-fast behavior
- Verify test coverage for all critical paths

Starting implementation review now.
---
<!-- COMMENTS:END -->
