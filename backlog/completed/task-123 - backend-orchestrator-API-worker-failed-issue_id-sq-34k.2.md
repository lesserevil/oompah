---
id: TASK-123
title: '[backend:orchestrator] API worker failed issue_id=sq-34k.2'
status: Done
assignee: []
created_date: 2026-03-09 22:05
updated_date: 2026-03-09 22:25
labels:
- archive:yes
- bug
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: bug
beads:
  id: oompah-ixw
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-ixw
  target_branch: null
  url: null
  created_at: '2026-03-09T22:05:36Z'
  updated_at: '2026-03-09T22:25:28Z'
  closed_at: '2026-03-09T22:25:28Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
API worker failed issue_id=sq-34k.2

Traceback (most recent call last):
  File "/Users/shedwards/src/oompah/oompah/prompt.py", line 100, in render_prompt
    for k, v in (memories or {}).items()
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/shedwards/src/oompah/.venv/lib/python3.13/site-packages/liquid/template.py", line 110, in render
    self.render_with_context(context, buf)
    ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "/Users/shedwards/src/oompah/.venv/lib/python3.13/site-packages/liquid/template.py", line 175, in render_with_context
    self.env.error(err, token=node.token)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/shedwards/src/oompah/.venv/lib/python3.13/site-packages/liquid/environment.py", line 486, in error
    raise exc
  File "/Users/shedwards/src/oompah/.venv/lib/python3.13/site-packages/liquid/template.py", line 158, in render_with_context
    node.render(context, buffer)
    ~~~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "/Users/shedwards/src/oompah/.venv/lib/python3.13/site-packages/liquid/ast.py", line 53, in render
    return self.render_to_output(context, buffer)
           ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "/Users/shedwards/src/oompah/.venv/lib/python3.13/site-packages/liquid/builtin/tags/if_tag.py", line 93, in render_to_output
    if self.condition.evaluate(context):
       ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^
  File "/Users/shedwards/src/oompah/.venv/lib/python3.13/site-packages/liquid/builtin/expressions/logical.py", line 143, in evaluate
    return is_truthy(self.expression.evaluate(context))
                     ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^
  File "/Users/shedwards/src/oompah/.venv/lib/python3.13/site-packages/liquid/builtin/expressions/logical.py", line 388, in evaluate
    return _lt(
        self.token, self.right.evaluate(context), self.left.evaluate(context)
    )
  File "/Users/shedwards/src/oompah/.venv/lib/python3.13/site-packages/liquid/builtin/expressions/logical.py", line 623, in _lt
    raise LiquidTypeError(
    ...<3 lines>...
    )
liquid.exceptions.LiquidTypeError: '<' and '>' are not supported between 'int' and 'NoneType'
  -> '{% if memories.size > 0 %}' 7:20
  |
7 | {% if memories.size > 0 %}
  |                     ^ '<' and '>' are not supported between 'int' and 'NoneType'


The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/shedwards/src/oompah/oompah/orchestrator.py", line 1697, in _run_api_worker
    )

    return wp, focus, prompt
    ^^^^^^^^^^^^^^^^^^^^^^^^


  File "/Users/shedwards/.local/share/uv/python/cpython-3.13.12-macos-aarch64-none/lib/python3.13/concurrent/futures/thread.py", line 59, in run
    result = self.fn(*self.args, **self.kwargs)
  File "/Users/shedwards/src/oompah/oompah/orchestrator.py", line 1689, in _setup_worker
    except Exception:
             ^^^^^^^^
    ...<3 lines>...
    prompt = render_prompt(
    ^
  File "/Users/shedwards/src/oompah/oompah/prompt.py", line 102, in render_prompt
    }

    ...<2 lines>...
        rendered = template.render(**variables)
        ^^^^^^^^^^
oompah.prompt.PromptError: Failed to render prompt template: '<' and '>' are not supported between 'int' and 'NoneType'
  -> '{% if memories.size > 0 %}' 7:20
  |
7 | {% if memories.size > 0 %}
  |                     ^ '<' and '>' are not supported between 'int' and 'NoneType'
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
