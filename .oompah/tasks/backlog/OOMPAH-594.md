---
id: OOMPAH-594
type: feature
status: Backlog
priority: 1
title: Reload HTTP Basic credentials safely after htpasswd rotation
parent: OOMPAH-586
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:55.490677Z'
updated_at: '2026-07-30T14:14:55.490677Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Prevent the running service from retaining stale HTTP Basic verifier state after the configured htpasswd file is atomically replaced or updated. Detect safe file identity/content changes, load and validate a complete replacement atomically, preserve the last known-good credentials on parse/read failure, and expose a redacted reload status. Ensure Makefile lifecycle clients and task/admin CLIs use the current .env client inputs; do not pass Basic credentials to workers. Relevant files include oompah/http_auth.py, bootstrap/server auth middleware, client lifecycle helpers, Makefile/scripts/oompah_http.py, and .env.example/operator docs if behavior changes.

Tests

Cover valid rotation, invalid/partial replacement, symlink/path protections, concurrent requests, username removal/addition, unchanged files, restart parity, and secret redaction. Run focused auth/server tests and make test.

Acceptance criteria

Supported credential rotation does not require an unauthenticated force restart; operator status, restart, task, and admin commands authenticate after rotation; malformed updates never disable or weaken auth.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

