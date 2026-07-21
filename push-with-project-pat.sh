#!/usr/bin/env bash
set -euo pipefail

export OOMPAH_PUSH_TOKEN
OOMPAH_PUSH_TOKEN="$(PYTHONPATH=. .venv/bin/python - <<'PY'
from oompah.projects import ProjectStore

project = ProjectStore().get("proj-14849f1b")
if project is None or not project.access_token:
    raise SystemExit("Oompah project PAT is not configured")
print(project.access_token)
PY
)"

git -c credential.helper= \
  -c 'credential.helper=!f() { printf "username=x-access-token\npassword=%s\n" "$OOMPAH_PUSH_TOKEN"; }; f' \
  push origin HEAD:main

unset OOMPAH_PUSH_TOKEN
