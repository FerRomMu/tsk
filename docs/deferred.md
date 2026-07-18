# Deferred / known gaps

Things consciously left for later. Each names where it should be resolved.

## Surface git's stderr on failure
`git.run_git` uses `capture_output=True` + `check=True`, so when a git command
fails, git's error message is captured into `CalledProcessError.stderr` and never
printed — a failing call raises a traceback with an empty-looking message.
Fine for a plumbing library (callers inspect), but the **CLI layer** must catch
`CalledProcessError` and surface `e.stderr` so failures are legible.
Resolve when building `cli.py` (Milestone D — error output).
