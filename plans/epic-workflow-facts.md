# Epic workflow facts

`oompah.epic_workflow` is the shared evidence boundary for shared and nested
epic rollups. `EpicFactCollector` walks the configured containment graph,
rejects repeated identifiers/cycles, and resolves targets from parent identity.
Each epic decision contains only that epic's direct children; deeper nodes are
walked solely for graph validation and are evaluated by their immediate epic.
The collector requests one `LandingFact` per direct child plus one for the epic
branch itself.

`evaluate_task` consumes the enriched containment fact for epic decisions. A
normal child must be `Done` and have positive landing evidence on its
immediate epic branch. A nested epic is checked by its positive landing fact
alone; its parent's derived tracker status is never an eligibility input.
This keeps the proof graph acyclic while allowing a nested branch to land on
an open parent branch.

Positive landing facts are append-only in the shared workflow job SQLite
ledger. A fresh process can therefore replay exact Git ancestry or
patch-equivalence evidence after the source ref is deleted. A live source that
advances does not invalidate proof for an explicitly requested immutable
revision; a target rewrite that drops Git proof does invalidate replay.
An unavailable target also fails closed until its current history can be
observed again; durable source-pruning evidence is not a substitute for a live
target authority check.
Bounded reads retain the newest proof window. Maintenance actions such as
rebase/repair, terminal validation,
cleanup, and restart recovery use the same generation-fenced job store through
`EpicWorkflowController`; abandoned recovery names both the dead lease owner
and the epic action domain.

When direct children are ready but the epic has not landed, the decision owns
rollup review creation. Once the epic branch is proven on its immediate target,
the decision changes to an evidence-bound `epic_auto_close` job. Enforce mode
does not issue a parallel direct terminal transition: the durable worker must
revalidate the exact decision immediately before that effect.

Legacy orchestrator gates use this path when `workflow_engine_mode` is
`enforce`; shadow scans use it for epics in `shadow` mode. Missing Git,
containment, or target evidence fails closed and schedules a bounded refresh
job rather than manufacturing an empty child set.
