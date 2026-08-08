---
id: OOMPAH-916
type: task
status: Backlog
priority: null
title: Unset removed .env configuration across graceful exec restarts
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T14:27:25.215337Z'
updated_at: '2026-08-08T14:37:32.516188Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

During workflow rollout, removing the four workflow-domain mode keys from .env and running make graceful did not disable shadow mode. The service uses os.execv for graceful restart, so the child inherits the old process environment; _load_startup_env calls load_dotenv(..., override=True), which updates present keys but never removes keys that disappeared from the authoritative .env file. The restarted process therefore retained stale rollout configuration until explicit off values were added.\n\nImplementation scope:\n- Synchronize environment keys managed by the authoritative dotenv file across in-process exec restarts, removing formerly file-managed keys that are absent after reload.\n- Preserve unrelated externally supplied environment variables and define fail-closed behavior for missing or unreadable dotenv files.\n- Use one shared restart environment path for Uvicorn and Granian exec flows.\n- Document the operator-visible semantics if needed.\n\nRequired tests:\n- Load a dotenv key, remove it from the file, reload in the same process, and prove it is removed.\n- Prove changed values override inherited values, unrelated external keys remain, and missing/unreadable files do not erase unmanaged configuration.\n- Cover both server restart backends or their common exec helper.\n\nAcceptance criteria:\n- Removing an OOMPAH_* key from .env takes effect after make graceful without requiring an explicit replacement value.\n- Graceful restart cannot retain stale rollout modes from a previous process image.\n- Focused config and lifecycle restart tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 14:37
---
Direct owner implementation completed locally on the systemic composition branch. Graceful Uvicorn and Granian exec restarts now reconcile the authoritative dotenv before exec, remove only formerly file-managed keys that disappeared, preserve unrelated variables, and keep last-known-good values for missing/unreadable files. 153 focused tests pass. Status remains Backlog until transition recovery is deployed.
---
<!-- COMMENTS:END -->
