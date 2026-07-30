# Decisions

> 🤖 Generated with Claude (Claude Code). Review critically before relying on it.

> Living document, not an ADR. Edit it as milestones complete; delete it once the tool
> exists. The immutable *why* lives in `docs/adr/` — this is the *what next*.

- **Lamport clock from the start.** Each op carries
  `lamport = 1 + max lamport over all ops reachable from the ref`. Required — concurrency
  is real once you sync.
- **No `tsk init`, no git-config side effects.** The backlog lives in the project's own
  repo, so `origin` is already there — inherited from the clone. tsk mutates no git config
  and registers no remote (the project repo is shared; changing its fetch config is a side
  effect on every contributor). Every fetch/push carries an explicit refspec and defaults
  to `origin`. A plain `git fetch` still won't pull `refs/tasks/*`; `tsk sync` does the
  fetch itself.
- **ID ergonomics: unique ULID prefix.** Commands accept a unique prefix
  (`tsk mv 01J3 doing`) and warn on ambiguity. Full 26-char IDs always accepted.
- **`tsk sync` will report what changed, not sync silently.** A mini-`ls` of the tasks a
  pull created / advanced / merged, instead of the current silent sync. Deferred until it
  can be meaningful: needs mutable refs (B) so a pull can change an existing task, and a
  fold that renders every op — status (B), title/body (D) — to show *what* changed. Shape:
  `sync.pull` returns the affected task ids, `cmd_sync` folds and prints them. A
  "new tasks only" version is possible from C-lite; the full new/updated/modified
  breakdown lands with D.
