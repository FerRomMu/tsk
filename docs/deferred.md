# Deferred / known gaps

> 🤖 Generated with Claude (Claude Code). Review critically before relying on it.

Things consciously left for later. Each names where it should be resolved.

## Surface git's stderr on failure
`git.run_git` uses `capture_output=True` + `check=True`, so when a git command
fails, git's error message is captured into `CalledProcessError.stderr` and never
printed — a failing call raises a traceback with an empty-looking message.
Fine for a plumbing library (callers inspect), but the **CLI layer** must catch
`CalledProcessError` and surface `e.stderr` so failures are legible.
Resolve when building `cli.py` (Milestone D — error output).

## DAG merge commit and push retry loop
Sync ships first as C-lite, on the create-only op set: task refs are write-once,
globally-unique ULIDs and cannot diverge. So the empty-tree merge commit for diverged
heads and the fetch→merge→push retry loop on non-fast-forward rejection (ADR-0002) are
not built — `sync.pull` adopts missing refs and `sync.push` pushes plainly. Both become
**mandatory** in Milestone B, the moment `set_status`/`mv` make refs mutable and
divergence becomes real. Syncing mutable tasks before they exist is unsafe.
Resolve in Milestone B.
