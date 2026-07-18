# Deferred / known gaps

Things consciously left for later. Each names where it should be resolved.

## Surface git's stderr on failure
`git.run_git` uses `capture_output=True` + `check=True`, so when a git command
fails, git's error message is captured into `CalledProcessError.stderr` and never
printed — a failing call raises a traceback with an empty-looking message.
Fine for a plumbing library (callers inspect), but the **CLI layer** must catch
`CalledProcessError` and surface `e.stderr` so failures are legible.
Resolve when building `cli.py` (Milestone D — error output).

## Commit identity: attribution vs. determinism
`git.commit_tree` sets no author/committer, so commits inherit `git config user.*`
and the system clock. This is deliberate: op identity is the blob OID (ADR 0004),
each commit is created once and transferred by OID, and ULIDs are unique per
creation — so a non-deterministic commit OID never causes divergence. Inheriting
config also gives free real attribution (who ran the op, when), which a team tool
likely wants. Open question: if we ever need deterministic/fixed identity, add
`GIT_AUTHOR_*`/`GIT_COMMITTER_*` env vars via an `env=` passthrough on `git.run`.
Revisit only if op.py needs to control identity.
