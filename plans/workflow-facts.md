# Versioned workflow facts

`oompah.workflow_facts` defines the evidence boundary consumed by the unified
workflow evaluator. A snapshot is complete only when every required domain is
represented: task, dependencies, containment, integration, terminal audit,
review/CI, landing, implementation authority, retry budget, and relevant
configuration.

Every domain is one of `known`, `missing`, `stale`, or `error`. Missing and
failed observations are never converted to an empty collection or a negative
answer. Revisions hash semantic content and source identity but exclude
observation timestamps, comments, and error prose. The combined
`facts_version` is therefore stable across harmless polling and suitable for
transition compare-and-swap.

Landing is target-specific and independent of parent task status.
`LandingFact(source, target, revision, proof, observed_at, project_id,
evidence_revision)` records positive, negative, or unknown evidence. Only
positive evidence can be durable, and proof cannot cross project scope. Exact Git ancestry, merge commits, patch
identity, forge merge records, and terminal-audit proof can survive normal
source-branch deletion; an unavailable source without such proof remains
unknown. Nested work is evaluated against its immediate configured target,
leaving root landing as a separate fact and removing the historical status
cycle.

`WorkflowFactCollector` is project scoped. Tracker identity/graph facts are
normalized directly, external evidence domains are injected as bounded
collectors, and provider exceptions become stable error codes without leaking
transport prose. `GitLandingCollector` uses real commit/ref evidence and can
preserve a matching durable prior proof when current source evidence becomes
unavailable.
