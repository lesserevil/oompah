---
id: OOMPAH-728
type: bug
status: Open
priority: 1
title: Keep structurally relevant peers in duplicate-screening corpus
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T16:19:05.113116Z'
updated_at: '2026-08-03T16:19:18.110676Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: EXOCOMP-216

Production regression observed on 2026-08-03 while screening EXOCOMP-216 and EXOCOMP-221. Three independent Duplicate Investigator runs for each task returned inconclusive because the injected tracker-backed corpus omitted the active sibling tasks needed for comparison. The agents explicitly named the missing peers (EXOCOMP-209 and EXOCOMP-213 through EXOCOMP-218 for EXOCOMP-216; EXOCOMP-219 through EXOCOMP-224 for EXOCOMP-221). One run then tried the scoped task CLI at http://localhost:8090 even though its sandbox had no reachable server. Both valid tasks exhausted the bounded retry budget and were moved to Needs Human. This violates OOMPAH-682's acceptance criterion that investigators receive enough authoritative active-task evidence to reach a verdict.

Implementation scope:
- Reproduce corpus construction for EXOCOMP-216 and EXOCOMP-221 against a project with more tasks than the corpus budget.
- Make relevance selection retain structurally relevant active peers before generic truncation: parent/children/siblings, declared dependencies and hard-start dependencies, and title/description similarity candidates.
- Include enough task description and relevant comment evidence for a conclusive comparison, while retaining deterministic size bounds and treating all task text as untrusted.
- Do not instruct or rely on a sandboxed investigator to query an unreachable loopback service; either make the injected corpus self-sufficient or provide a supported authenticated read-only transport and advertise only capabilities actually available.
- Expose an actionable diagnostic when required peers cannot fit the corpus instead of consuming three indistinguishable model retries.

Required tests:
- Large-corpus regressions modeled on EXOCOMP-216 and EXOCOMP-221 prove every same-parent sibling and dependency relevant to screening is present.
- Deterministic budget tests prove unrelated tasks are evicted before structurally relevant peers.
- A network-disabled investigator prompt remains self-sufficient and does not require CLI fallback.
- Corpus entries preserve status, description, and bounded relevant comments.
- Existing prompt-injection, revision-fingerprint, late-claim, retry, and owner-resolution tests continue to pass.
- Run focused duplicate-preflight/prompt tests and make test.

Acceptance criteria:
- Each reproduced task reaches a conclusive screening verdict in one normal run using only supplied evidence.
- No valid task reaches Needs Human solely because relevant active peers were dropped by corpus selection.
- Corpus size remains bounded, deterministic, project-scoped, and safe for untrusted task text.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

