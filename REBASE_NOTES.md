# Rebase Notes: umpah-pyo onto main

## Issue: umpah-1bg

Resolved merge conflicts in the `umpah-pyo` branch (PR #1: fix model list scrolling in provider dialog).

## Root Cause

The `umpah-pyo` branch contained 4 backup-only commits (modifying `.beads/backup/` files) that conflicted with newer backup commits on `main`. These intermediate snapshot commits were not meaningful to preserve.

## Resolution

Used `git rebase --onto origin/main` with an interactive rebase to:
1. Drop the 4 backup-only commits from `umpah-pyo` (commits: 78f77a9, 532a0d8, aeda280, 2a51bdf)
2. Keep only the 2 meaningful code commits:
   - `a962fdb`: umpah-pyo: make model list scrollable in provider dialog
   - `e37d864`: umpah-pyo: improve model list scrolling with viewport-relative max-height and overlay scrolling
3. Force-pushed the rebased branch to origin/umpah-pyo

## Result

PR #1 is now MERGEABLE with CLEAN merge state status.
The diff vs main shows only the intended CSS changes to `oompah/server.py`.
