# Skills plugin pattern (experimental)

> **Status: experimental — not committed.** This document records a proposed
> direction for replacing the inline tool registry in `oompah/api_agent.py`
> with a `Skill` ABC + registry. It has not been implemented and may be
> rejected, replaced, or significantly reshaped before any work begins.
> Recorded for reference so the discussion isn't lost.

## Why

The current agent skill surface is 8 hardcoded tools defined as an inline
list of OpenAI function-calling schemas (`oompah/api_agent.py:104-525`),
each paired with a sibling `_exec_*` handler dispatched through
`_execute_tool`. Three pain points:

1. The list is inline Python with the schema, so every new tool means
   editing `api_agent.py` directly. No external extension point.
2. Per-skill metadata (`opt_in`, required-args, productive-for-stall-detection,
   capability gate) lives in three separate module-level constants
   (`_OPT_IN_TOOLS`, `_TOOL_REQUIRED_ARGS`, `_PRODUCTIVE_TOOLS`) plus a
   hardcoded check for `attach_image` in `orchestrator.py:2075-2076`.
3. There's no per-focus way to scope which skills an agent gets, beyond
   the orchestrator's manual set construction. WORKFLOW.md has no syntax
   for it.

## Decisions taken in conversation

| | Decision |
|---|---|
| **a. Layered, not replacing** | New native skills sit alongside `run_command`. Tracker-native skills and `git_*` skills are preferred when they exist, but the tracker-specific cheat sheet stays in WORKFLOW.md as a fallback. |
| **b. Defaults location** | Built-in skill defaults stay hardcoded in Python. Per-focus override goes in WORKFLOW.md frontmatter as `skills: [...]`. No `.oompah/skills.yaml` for now. |
| **c. Safety posture** | Unchanged. No new permission system. Anything an agent can do via `run_command` it can do via a native tool. |
| **d. Specific skills** | Deferred. Wire the registry first; add concrete skills later. |
| **Capability gate** | Made generic: any skill may declare `requires_capability="image"` etc. The hardcoded `attach_image` gate in `orchestrator.py` becomes a registry call. |

## Proposed shape

### New module `oompah/skills/`

```
oompah/skills/
  __init__.py     # public API: Skill, SkillContext, registry
  base.py         # Skill ABC + SkillContext + SkillRegistry
  builtin.py      # 8 existing tools refactored as Skill subclasses
```

### Skill ABC (`base.py`)

```python
class Skill(ABC):
    name: str                                 # e.g. "read_file"
    description: str                          # what the model sees
    parameters: dict                          # JSON-schema for arguments
    required_args: list[str] = []
    opt_in: bool = False                      # default-disabled (e.g. attach_image)
    requires_capability: str | None = None    # gate on focus/model capability
    productive: bool = False                  # counts toward stall detection?

    @abstractmethod
    def execute(self, args: dict, ctx: SkillContext) -> str: ...

    def to_openai_tool(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }}


@dataclass
class SkillContext:
    workspace: Path
    command_timeout: int
    # Future: project_id, agent_log path, focus name — added as needed.
```

### Registry

```python
class SkillRegistry:
    def register(self, skill: Skill) -> None: ...
    def get(self, name: str) -> Skill | None: ...
    def all(self) -> list[Skill]: ...
    def select(
        self,
        enabled: set[str] | None,
        capabilities: set[str],
    ) -> list[Skill]:
        """
        - enabled=None → all non-opt-in skills.
        - enabled=set  → only those names; opt-in allowed if listed.
        - capabilities filter applies regardless: requires_capability
          not in caps → drop.
        """
```

### Refactor `oompah/api_agent.py`

- `TOOL_DEFINITIONS` becomes a computed property over `_global_registry.all()`,
  kept as a module export for backwards compat.
- `_execute_tool(workspace, name, args, cmd_timeout)` becomes a thin shim:
  `_global_registry.get(name).execute(args, ctx)`.
- The 8 existing `_exec_*` functions move into `builtin.py` as
  `class ReadFileSkill(Skill): ...` etc. Their bodies are unchanged.
- `_OPT_IN_TOOLS`, `_PRODUCTIVE_TOOLS`, `_TOOL_REQUIRED_ARGS` go away —
  replaced by per-skill class attributes.
- `ApiAgentSession._tool_definitions` (api_agent.py:797) calls
  `_global_registry.select(self.enabled_tools, self.capabilities)`.

### WORKFLOW.md per-focus override

```yaml
foci:
  - name: chore
    role: Maintenance Engineer
    skills: [read_file, list_files, edit_file, run_command, ask_question]
    # If omitted: all non-opt-in skills (today's behavior).
```

The existing `enabled_tools` plumbing in the orchestrator is untouched;
the new field just feeds that set.

## Backwards-compat invariants

- 8 existing tools have identical names, schemas, and behavior post-refactor.
- `TOOL_DEFINITIONS` export returns the same list contents (just generated).
- `_execute_tool` keeps its signature.
- No WORKFLOW.md change required for existing configs; the new `skills:`
  field is optional.

## Tests required

1. Registry: register, lookup-by-name, all, select with/without filters,
   capability gate.
2. Each builtin Skill has the same JSON schema as the current
   `TOOL_DEFINITIONS` entry (golden-test it).
3. `_execute_tool` produces the same output for each of the 8 tools
   given a fixture workspace (regression catch).
4. End-to-end: an `ApiAgentSession` with mocked HTTP gets the same
   `tools` payload as before the refactor.

## Files

| Action | Path |
|---|---|
| New | `oompah/skills/{__init__,base,builtin}.py` |
| New | `tests/test_skills.py` |
| Refactor | `oompah/api_agent.py` |
| Touch | `oompah/focus.py` (one new field) |
| Touch | `oompah/orchestrator.py` (read the new field; replace `attach_image` gate with `requires_capability`) |
| Verify untouched | `tests/test_asking_questions.py`, `tests/test_attachments.py`, `tests/test_api_agent_budget.py` |

## Estimated scope

~1 day. Registry + base classes are small; bulk is mechanical refactor
of `_exec_*` into subclasses + porting tests.

## Reasons we might NOT want this

- Adds an indirection layer for a tool surface that's only 8 entries deep.
  YAGNI may be the right call until there's a concrete second-source of
  skills (MCP integration, project-defined tools).
- The current inline list is fully grep-able; a registry pattern moves
  schemas further from their handlers.
- Per-focus override has no current consumer beyond the existing binary
  `attach_image` gate. We may not need the WORKFLOW.md syntax until a
  real use case appears.

## Reasons we might want this anyway

- Sets up cleanly for MCP or per-project skills later without re-touching
  `api_agent.py`.
- Removes three module-level constants that already encode per-skill
  policy in scattered form.
- Makes "what skills does this focus use?" explicit in WORKFLOW.md
  rather than implicit in orchestrator code.

## Decision needed

Whether to commit to this direction at all. The user has flagged this
as experimental and is not yet convinced.
