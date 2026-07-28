---
id: OOMPAH-533
type: task
status: Backlog
priority: 3
title: Expose duplicate-screening state in the API and dashboard
parent: OOMPAH-528
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T21:19:45.110386Z'
updated_at: '2026-07-28T21:19:45.110386Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Make pre-dispatch duplicate screening understandable to operators after the lifecycle from OOMPAH-529 through OOMPAH-532 is functional.

Implementation scope:
- Add a stable API representation of duplicate screening to issue detail/state payloads: unchecked, running, checked, or stale; include checked_at, detector identity/version, claim start/expiry for running work, and matched identifiers for duplicate verdicts. Do not expose internal prompts, secrets, or full agent output.
- Ensure active-agent/activity endpoints identify a duplicate preflight run as screening rather than implementation while the underlying task remains Open.
- Update the dashboard task card/detail UI to display a compact Duplicate check badge/state. Running must update through the existing refresh/WebSocket mechanism; checked/stale must render after reload.
- Add accessible text/title details explaining why a result is stale and when it was checked. Do not rely on color alone.
- Add aggregate state/metrics fields needed to explain why an Open task is not yet eligible for implementation, including waiting for duplicate check and duplicate check running.
- Keep payload parsing backward compatible when older servers or tasks have no screening metadata.

Relevant context/files:
- oompah/server.py issue/state/activity endpoints.
- oompah/templates/dashboard.html and existing client-side issue rendering.
- Metadata helpers from OOMPAH-529 and orchestrator run state from OOMPAH-530/OOMPAH-532.
- Existing API/dashboard tests should be extended rather than replaced.

Required tests:
- API serialization for all four states, malformed/legacy metadata, and safe field filtering.
- Activity payload distinguishes preflight from implementation.
- Dashboard rendering tests for unchecked, running, checked, stale, and missing metadata.
- Refresh/update regression proving an Open task changes badges when screening starts/completes without changing to In Progress.
- Accessibility assertion for textual status information.

Acceptance criteria:
1. Operators can distinguish Open-and-waiting, Open-and-screening, and Open-and-checked tasks.
2. The agent list does not claim that implementation is underway during duplicate preflight.
3. API additions are backward compatible and do not expose sensitive worker data.
4. UI state updates without a full service restart and remains correct after page reload.
5. Focused API and dashboard tests pass through the appropriate Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

