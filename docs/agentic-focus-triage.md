# Agentic focus triage (experimental)

> **Status: experimental — not committed.** This document records a proposed
> direction for replacing the deterministic keyword-scoring focus selector
> in `oompah/focus.py` with an LLM call that reads the issue and the focus
> definitions and picks the best fit. It has not been implemented and may
> be rejected, replaced, or significantly reshaped before any work begins.

## Why

Today's `score_focus(focus, issue)` is a deterministic scorer:

| Signal | Points |
|---|---|
| `needs:<focus>` handoff label | +200 |
| Each keyword hit in title+description | +10 |
| Issue type match | +50 |
| Label match | +30 each |
| Focus priority (tiebreaker only when score>0) | +N |

Foci with poor or sparse keyword lists silently lose contests they
should win. New user-defined foci often start with weak keywords and
get the wrong work routed to them. Several mismatches we've already
seen — e.g. `event_queue` focus picked for a "say hello" dummy task —
fall out of keyword sparsity, not real ambiguity.

An LLM reading the issue's title/description and each focus's
role/description/must-do can reason about fit semantically. The
deterministic scorer becomes the safety net.

## Decisions taken in conversation

| | Decision |
|---|---|
| **Model** | Provider's `default_model` (skip `_resolve_model`'s profile chain). Cheap path. |
| **Foci library** | No change to `.oompah/foci.json` shape. |
| **WORKFLOW.md** | No change required for v1. |
| **Always-on?** (Q1) | Yes. No flag. Deterministic fallback is the safety net. |
| **Cache TTL** (Q2) | Content-keyed, no TTL. Re-triage only when issue text or foci library changes. |
| **LLM may decline** (Q4) | Yes. The literal output `default` is a valid response and routes to `DEFAULT_FOCUS`. |
| **Surface in agent prompt** (Q5) | No. Agent gets the focus the same way it does today; it doesn't need to know how triage was made. |
| **Confidence threshold** (Q3) | **C + D**: LLM outputs `name: reasoning` (logged at INFO). Then `score_focus(picked_focus, issue)` is computed. If score == 0 (literal hallucination — no keyword/label/type alignment at all), fall back to deterministic top pick. Otherwise trust the LLM. |

## Proposed shape

### Flow inside `select_focus(issue)`

```
1. Explicit routing — short-circuit, no LLM:
   if any "needs:<X>" label matches an active focus name → return that focus.
   (User intent always wins.)

2. LLM triage:
   prompt   = build_triage_prompt(issue, active_foci)
   response = call_default_model(prompt, max_tokens=64)
   selected = parse_response(response)
   if selected is in {f.name for f in active_foci} → return that focus.

3. Fallback — current deterministic score_focus:
   If LLM call fails, times out, or returns an unknown name → fall back
   to today's logic, which itself falls back to DEFAULT_FOCUS.
```

### Triage prompt sketch

```
You are routing an engineering issue to the best-fit specialist.

ISSUE
  identifier: {{ issue.identifier }}
  title: {{ issue.title }}
  type: {{ issue.issue_type }}
  priority: {{ issue.priority }}
  labels: {{ issue.labels | join: ", " }}
  description:
{{ issue.description | indent 2 }}

SPECIALISTS
  {% for f in foci %}
  - name: {{ f.name }}
    role: {{ f.role }}
    description: {{ f.description | truncate: 200 }}
    typical work: {{ f.must_do | first 3 | join: "; " }}
  {% endfor %}

TASK
Pick the single best-fit specialist by name. Output ONLY the name on
one line, no prose, no quotes. If no specialist clearly fits better
than the others, output "default".
```

`max_tokens=64` keeps the response tight and cost low. Existing
context-budget logic in api_agent applies, so a long prompt won't
blow up.

### What "default model" means here

The provider's `default_model` field, NOT the agent profile's resolved
model. So a fast/cheap model can be configured separately from what
dispatched agents use. Same provider; different model selection.
Code path: skip `_resolve_model(profile, provider)` and just use
`provider.default_model or provider.models[0]`.

### Files to touch

- `oompah/focus.py` — make `select_focus` async; new private
  `_select_focus_llm(issue, foci, provider) -> str | None`; new
  `_build_triage_prompt(issue, foci) -> str`; cache.
- `oompah/orchestrator.py` — `select_focus(issue)` call site at
  `_run_api_worker:1955` becomes `await select_focus(issue, ...)`. Pass
  the resolved provider so the helper can call its `default_model`.
- New tests: `tests/test_focus_triage.py` — golden tests for the
  prompt rendering; LLM call tests with `_http_post` mocked covering
  valid / unknown-name / empty / timeout responses; cache-hit test.

### What does NOT change

- `score_focus` stays — it's the fallback. Don't touch its tests.
- Foci definitions (`.oompah/foci.json` shape) don't change.
- WORKFLOW.md prompt template doesn't change.
- The orchestrator's profile resolution (separate from focus) doesn't change.

## Estimated scope

~½ day. The prompt template + parser + fallback are small; cache is
a dict; the test surface is moderate. Most of the time is making sure
the "LLM unavailable" path is rock-solid.

## Reasons we might NOT want this

- Adds ≥1 LLM call per dispatch, which is real cost at scale.
- Today's keyword scorer has been working for the cases that matter;
  the times we've seen wrong focus selection are mildly cosmetic, not blocking.
- More moving parts to debug when things misbehave: now there's
  "did the model pick wrong" *and* "did the scorer pick wrong."

## Reasons we might

- Foci with poor keyword lists silently lose scoring contests they
  should win. LLM closes that gap without forcing operators to maintain
  perfect keyword sets.
- New foci added by users get sensible behavior immediately even if
  their keywords are weak.
- Aligns with the system's general direction (more semantic, fewer
  hand-tuned heuristics).

---

## Q3 rationale (resolved: C + D)

All Q1–Q6 are now locked (see decisions table above). The Q3 reasoning
is preserved here because it was the most nuanced choice; the rest were
straightforward.

The question is what to do when the LLM is uncertain. Concretely, the
"trust" boundary determines when we fall through to the deterministic
score even though the LLM gave us a name.

#### Option A: Name-only, full trust

LLM outputs just `feature` or `default` or whatever. We use it.

- Cheapest (smallest output, fewest tokens).
- Simplest parser.
- Risk: a confidently-wrong pick is indistinguishable from a confident
  correct pick. We never second-guess.

#### Option B: Name + explicit confidence token

LLM outputs `feature high` or `feature low` (or `feature mid`). On
`low`, fall back to deterministic score.

- Requires the LLM to self-report calibration, which small/cheap models
  do poorly. Risk: it always says `high` and we get Option A's behavior
  for double the parsing complexity. Or it always says `low` and we
  effectively never use the LLM.
- Modest extra tokens.
- Clear contract, easy to audit.

#### Option C: Name + 1-line reasoning, log the reasoning

LLM outputs `feature: this is new functionality, not a bug fix`.
Always trust the name. Log the reasoning at INFO so we can audit later.

- Best-of-both: maximum auditability, no behavioral change from A.
- More output tokens — maybe 50-100 vs 10. At cheap-model rates,
  ~$0.0001 extra per dispatch.
- Helps when triage misbehaves: the log tells you why.

#### Option D: Sanity-check via deterministic score

LLM outputs a name (Option A format). Before trusting it, compute the
deterministic `score_focus` for the chosen focus. If the LLM's pick
scores `0` (no keyword/label/type alignment at all), log a warning and
fall back to the deterministic top pick.

- Uses signals we already compute, no extra prompt complexity.
- Catches the "LLM hallucinated a focus name that's nonsensical for
  this issue" failure mode.
- Doesn't catch the more common case: LLM picks something *plausible*
  but wrong (e.g. `frontend` over `backend` on a CSS issue that the
  agent then can't fix because the bug is in JS state, not styling).
  But neither do options A–C, so this is no worse.

#### Option E: A + D combined

LLM outputs name only (A), but we sanity-check (D). Best parser
simplicity + cheap protection against hallucinated names.

#### Final pick: C + D, with score == 0 as the fallback threshold

Name-only would miss the whole point — the LLM's value over a keyword
scorer is its judgment, and capturing that judgment in the log is
exactly what makes audit possible when triage looks wrong. C and D
have no overlap and combine cleanly:

- **C** logs the reasoning (~50-100 extra output tokens per call) so
  audit later can answer "did the LLM mis-reason, or did we
  mis-evaluate the LLM?"
- **D** catches the LLM hallucinating a focus name that's literally
  nonsensical for this issue. Uses `score_focus` we compute anyway.

Threshold for D's fallback: **score == 0** (the LLM picked a focus
with zero keyword/label/type alignment). Stricter thresholds (top-3,
top-1) would cancel the LLM's purpose, since the whole reason to use
it is to override the scorer when keywords are weak.
