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

## Push retry loop on non-fast-forward rejection
The empty-tree merge commit for diverged heads (ADR-0002) has landed: `sync.pull` now
joins two diverged task heads with a two-parent, empty-tree merge commit. But the merge
descends from the remote head we *fetched*, not from whatever the server holds at push
time — so if another clone pushes between our fetch and our push, `sync.push` is rejected
non-fast-forward. The fetch→merge→push retry loop that closes that window is still not
built: `sync.push` pushes plainly and surfaces git's rejection unretried. It became
**mandatory** the moment `set_status`/`mv` made refs mutable and real divergence possible.
Resolve in Milestone B (next step).

Note: `git.push` goes through `git.run` (`capture_output=True`), so a non-fast-forward rejection
currently raises `CalledProcessError` with the reason in `.stderr` — the retry loop must
distinguish that specific rejection from other push failures.
