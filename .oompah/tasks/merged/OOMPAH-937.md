---
id: OOMPAH-937
type: bug
status: Merged
priority: 1
title: Project current exhausted jobs as actionable liveness failures
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-09T07:29:03.390818Z'
updated_at: '2026-08-09T08:50:54.278285Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-c47cef180b86
    project_id: proj-14849f1b
    task_id: OOMPAH-937
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5da9fecba7e20132d54a19ac5ad617cc1be333e484afcb20b22086a7e58e7329
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner direct delivery is on protected main at b7e7d950 after
      PR #750 and all hosted tests passed; live state confirms authoritative exhausted
      rows are actionable and stale rows clear only after concrete replacement authority.'
    created_at: '2026-08-09T08:50:36.450422+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-937
    target_state: Merged
    evidence_fingerprint: 5da9fecba7e20132d54a19ac5ad617cc1be333e484afcb20b22086a7e58e7329
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T08:50:47.163557+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-931

Production after OOMPAH-931 reports workflow_jobs.current_states.exhausted=104 while the same affected tasks are projected by workflow liveness as disposition=retry_scheduled, alert_level=info, action_required=false, and unexplained divergence. The universal controller currently recognizes stored exhaustion only when the schedule cursor decision revision exactly equals the newly evaluated decision revision; ordinary evidence/reassessment revision changes can therefore mask an exhausted generation that remains authoritative in the store current-state projection. Implement one authoritative per-task current-generation exhaustion lookup shared with workflow job health, and make liveness projection classify that condition as retry.exhausted/action_required until a distinct replacement generation actually owns recovery. Preserve historical exhausted ledger rows as non-actionable when superseded, fail closed on ambiguous cursor/generation state, and prevent repeated reevaluation from silently downgrading current exhaustion. Add regression tests covering an exhausted integration landing refresh followed by evidence/reassessment revision changes, historical superseded exhaustion, a queued replacement generation, restart/persistence, current_states parity, and state/API alert projection. Acceptance: every current_states.exhausted job maps to an actionable task/liveness explanation or an explicitly documented non-task system owner; no current exhaustion is shown as normal retry activity; superseded historical exhaustion remains non-actionable; focused tests and the complete branch gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 07:49
---
Direct-owner implementation complete at clean pushed head daea753e7. Global current_states.exhausted and per-task liveness now share one durable authority query; revision drift cannot hide current exhaustion; concrete replacement generations clear only historical rows; ambiguous/retired replacements fail closed; universal retry.exhausted overrides ordinary owner retry in API publication. Verification: 191 focused store/controller/runtime/state-projection tests passed; git diff --check passed. Awaiting combined protected-main integration with OOMPAH-935/OOMPAH-936.
---
author: oompah
created: 2026-08-09 08:31
---
Combined delivery is pushed at final head cafc100c4 on PR #750. Protected hosted CI is running the complete gate on Python 3.11, 3.12, and 3.13.
---
author: oompah
created: 2026-08-09 08:50
---
Delivered to protected main by merged PR #750 at b7e7d9509a4e6025b48c54336098acef2dda4986; complete hosted gates passed on Python 3.11/3.12/3.13. Live generation 246 now projects every detected authoritative exhaustion as retry.exhausted/action_required/operator instead of normal retry info; replacement generations remove historical rows from current exhaustion as intended.
---
author: oompah
created: 2026-08-09 08:50
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Project-owner direct delivery is on protected main at b7e7d950 after PR #750 and all hosted tests passed; live state confirms authoritative exhausted rows are actionable and stale rows clear only after concrete replacement authority.
---
author: oompah
created: 2026-08-09 08:50
---
Merged in PR #750 at b7e7d950; hosted CI and live actionable-exhaustion projection passed.
---
<!-- COMMENTS:END -->
