---
id: OOMPAH-341
type: task
status: Backlog
priority: null
title: Implement GitLabHookManager with OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL config
parent: OOMPAH-325
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T00:28:44.100086Z'
updated_at: '2026-07-22T00:28:44.100086Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement a GitLabHookManager class that manages GitLab project hooks (create/reconcile/remove) via the GitLab Project Hooks API, and add OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL configuration.

## Scope

New file: oompah/gitlab_hook_manager.py
Modify: oompah/config.py (or wherever env-var config is read)
New tests: tests/test_gitlab_hook_manager.py

## What to implement

### Config
Add OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL:
- Read from environment in config.py alongside other OOMPAH_* settings
- Must be a public HTTPS URL with no trailing slash (e.g. https://oompah.example.com)
- When absent, hook creation is skipped and a WARNING is logged once at startup

### GitLabHookManager class

```python
class GitLabHookManager:
    def __init__(self, public_url: str, session: httpx.AsyncClient):
        ...

    async def create_hook(self, project: Project) -> HookRecord:
        """Call POST /api/v4/projects/:id/hooks with all subscribed event flags."""
        ...

    async def reconcile_hook(self, project: Project) -> HookRecord:
        """GET existing hooks, update if URL/events mismatch, create if missing."""
        ...

    async def delete_hook(self, project: Project, hook_id: int) -> None:
        """DELETE /api/v4/projects/:id/hooks/:hook_id."""
        ...
```

Key behaviors:
- Per-project webhook secret: generate a cryptographically random 32-byte token (secrets.token_hex(32)) and store in project.webhook_secret when creating a hook. Rotate on explicit reconcile if the token has been cleared.
- Subscribed events: push_events, merge_requests_events, issues_events, note_events, pipeline_events, job_events, confidential_issues_events=True
- Use the project's forge_base_url (from project.forge_base_url) for the API base, not a global GitLab URL
- URL-encode nested project paths using urllib.parse.quote(path, safe='')
- Apply existing timeout and retry behavior consistent with GitLabProvider
- Redact secrets from error messages before logging (never log webhook_secret or token values)
- HookRecord: a dataclass with hook_id, url, created_at, events_match fields

### Error handling
- On 4xx API errors, log a WARNING with the status code and a sanitized message (no credentials)
- On 5xx, log an ERROR with redacted details
- On missing OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL, return a sentinel HookRecord indicating skip (not an exception)

## Tests to write (tests/test_gitlab_hook_manager.py)

Use httpx.MockTransport or unittest.mock to simulate GitLab API responses:

- test_create_hook_success: POST hook with correct event flags and secret; returns HookRecord with hook_id
- test_reconcile_finds_existing_hook_by_url: GET returns matching hook; no POST/PUT required
- test_reconcile_updates_mismatched_event_flags: GET returns hook with wrong events; PUT to update
- test_reconcile_creates_when_no_hooks_exist: GET returns []; POST to create
- test_delete_hook: DELETE /hooks/:id succeeds
- test_create_hook_4xx_redacts_secret_from_log: 401 response logs WARNING without revealing the token
- test_create_hook_5xx_redacts_credentials: 500 response logs ERROR without revealing the token
- test_missing_public_url_returns_skip_record: no OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL → skip
- test_nested_group_path_is_url_encoded: path 'group/subgroup/project' encodes correctly

## Acceptance criteria
- All tests in tests/test_gitlab_hook_manager.py pass
- make test passes with no regressions
- No webhook secret or token appears in any log output (verified by test assertions on log captures)

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

