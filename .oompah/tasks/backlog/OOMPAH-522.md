---
id: OOMPAH-522
type: feature
status: Backlog
priority: 1
title: Load and verify optional htpasswd credentials safely
parent: OOMPAH-521
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T18:11:34.097786Z'
updated_at: '2026-07-28T18:11:34.097786Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

