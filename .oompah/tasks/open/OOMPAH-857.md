---
id: OOMPAH-857
type: task
status: Open
priority: null
title: Clear recovered operator-auth warnings after authenticated success
parent: OOMPAH-740
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T07:17:16.417571Z'
updated_at: '2026-08-06T07:17:30.728550Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

A failed operator Basic-auth probe currently leaves auth_health:operator styled as an actionable warning for the full rolling window even after the same configured principal successfully authenticates. The message then prescribes regenerating htpasswd and restarting a healthy server, which is false and displaces the dashboard despite current proof that credentials work.\n\nImplementation scope:\n- Separate rolling authentication failure telemetry from current credential-health actionability.\n- Record successful authenticated operator probes with principal/config generation context and reclassify or clear stale credential-mismatch warnings when current credentials demonstrably succeed.\n- Preserve security visibility for unexplained failures from other principals/sources and for continuing failures with no subsequent success; never expose credentials or weaken authentication.\n- Ensure the dashboard receives the authoritative removal/reclassification through the existing sequenced state stream without refresh.\n\nRelevant code: operator Basic-auth middleware/counters and auth-health serialization in oompah/server.py and related auth-health modules, dashboard alert normalization/rendering in oompah/templates/dashboard.html, and auth/alert tests under tests/.\n\nRequired tests:\n- Failed configured-principal request followed by successful authenticated request clears or demotes the credential-mismatch action without waiting 15 minutes.\n- Continuing failures remain actionable with correct remediation.\n- Failures attributable to a different/unknown principal remain security telemetry without being falsely declared recovered.\n- A sequenced authoritative state update removes the stale warning in the browser model.\n\nAcceptance criteria:\n- A healthy authenticated operator session never displays instructions to regenerate working credentials or restart solely because of an earlier recovered probe.\n- Historical failure counts remain available as bounded diagnostics, while only current operator actionability occupies the warning surface.\n- Focused auth-health, state-stream, and dashboard alert tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

