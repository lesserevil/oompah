"""Git hooks installed into agent worktrees.

The scripts here are not Python modules in the import sense — they are
standalone executables that git invokes. The package's ``__file__`` and
``__path__`` are used by :mod:`oompah.projects` to locate the hook source
files for symlinking into ``.oompah-no-hooks/`` of each agent worktree.
"""

import os

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))


def hook_path(name: str) -> str:
    """Return the absolute path to a hook script bundled with oompah.

    Example: ``hook_path("prepare-commit-msg")``.
    """
    return os.path.join(_PACKAGE_DIR, name)
