# Duplicate Screening

Oompah qualifies ordinary `Open` tasks with a model-backed duplicate check
before assigning an implementation agent. Screening is separate from
implementation: the task stays `Open`, while the dashboard shows whether the
check is pending, running, complete, or stale.

The existing inexpensive title and label similarity filter still runs first.
A heuristic miss does not count as a model-backed pass.

## Lifecycle

```mermaid
stateDiagram-v2
    [*] --> OpenUnchecked: Task enters Open
    OpenUnchecked --> OpenRunning: Spare agent capacity and claim acquired
    OpenRunning --> OpenChecked: No active duplicate
    OpenRunning --> DuplicateCandidate: Active duplicate verified
    OpenRunning --> OpenUnchecked: Inconclusive, failed, or expired claim
    OpenChecked --> OpenStale: Duplicate-relevant task fields change
    OpenStale --> OpenRunning: Spare capacity and retry allowed
    OpenChecked --> InProgress: Implementation agent claims task
```

The duplicate comparison pool contains only non-terminal tasks. `Done`,
`Merged`, and `Archived` tasks may provide historical context, but Oompah will
not use them as canonical duplicate targets.

## Capacity

Configure the maximum number of simultaneous screening agents in `.env`:

```dotenv
OOMPAH_DUPLICATE_PREFLIGHT_MAX_AGENTS=1
```

The default is `1`. Set it to `0` to disable model-backed background
screening.

On each scheduler tick, Oompah:

1. Re-evaluates current concurrency and renews long-running screening claims.
2. Dispatches checked implementation work and epic planning first.
3. Uses remaining slots for unchecked or stale `Open` tasks, up to the
   screening cap.

Screening therefore cannot displace an implementation task that was already
ready during the same tick. If capacity shrinks below the number of running
agents, Oompah does not terminate either screening or implementation agents;
it simply starts no additional work until capacity is available.

## Screening States

The task card and detail panel expose these states:

- `unchecked`: no current model-backed result exists.
- `running`: a screening agent owns a live claim; the task remains `Open`.
- `checked`: the current task revision received a conclusive verdict.
- `stale`: the task changed, the detector version changed, metadata is legacy
  or malformed, or the claim expired.

The agent bar labels a running qualification as `screening`. It does not move
the task card to `In Progress`.

## Result Validity

Oompah fingerprints the normalized task title, description, type, project,
parent, dependencies, and user-authored scope labels. Comments, timestamps,
priority, tracker state, and transient Oompah labels are excluded.

Editing a fingerprinted field invalidates the previous pass automatically.
The implementation dispatcher accepts only a current `no_duplicate` result.
The legacy `focus-complete:duplicate_detector` label has no revision
fingerprint, so it is treated as stale and screened again.

Claims include an opaque identifier and expiry. Completion is compare-and-set
against that identifier and the original fingerprint. A late worker cannot
clear a replacement claim or qualify an edited task. Expired claims become
eligible for another screening run after restart.

## Failure and Human Review

Malformed, inconclusive, timed-out, or failed runs release their claims and
retry with bounded exponential backoff. After three inconclusive attempts,
Oompah moves the task to `Needs Human`. The final task comment instructs the
human to review the screening history and either identify the active canonical
task or confirm that no active duplicate exists before returning the task to
`Open`.

## Troubleshooting

If an `Open` task is not starting:

1. Check its **Duplicate check** badge.
2. If it is `running`, check the matching agent chip and activity log.
3. If it is `stale`, confirm that the retry backoff has elapsed and agent
   capacity is available.
4. Confirm `OOMPAH_DUPLICATE_PREFLIGHT_MAX_AGENTS` is greater than zero.
5. Check normal dispatch gates such as dependencies, project pause, provider
   availability, budget, and shared-epic serialization.

Scheduler diagnostics include duplicate-preflight counts for selected,
started, checked, running, backoff, no-capacity, and claim-race outcomes.
