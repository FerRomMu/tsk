# ADR-0005: No git-config side effects; explicit refspecs, no `tsk init`

> 🤖 Generated with Claude (Claude Code). Review critically before relying on it.

## Status

Accepted — 2026-07-22

## Context

The backlog lives inside the project's own repository (ADR-0001): cloning the project
clones the backlog, and `origin` is inherited from that clone. ADR-0001 noted a
consequence — `refs/tasks/*` is not fetched by a default `git fetch`, so "an explicit
refspec must be configured," which it called the tool's primary adoption friction. The
original plan discharged this in `tsk init`, which would write
`remote.origin.fetch = +refs/tasks/*:refs/remotes/origin/tasks/*` into the repo's config.

Two problems with configuring that refspec:

- The repo is shared. Persisting a fetch refspec (or adding a remote) mutates the git
  config of a repo every contributor uses, changing what their plain `git fetch` does —
  a side effect tsk has no business causing.
- It is load-bearing but invisible. A contributor who never ran `tsk init`, or whose
  config was reset, silently sees an empty backlog — exactly the friction ADR-0001
  warned about, now made a required setup step.

## Decision

tsk mutates no git config and registers no remote. Every git command that crosses the
network passes an explicit refspec on the command line and defaults the remote to
`origin`:

- fetch: `git fetch origin +refs/tasks/*:refs/remotes/origin/tasks/*`
- push:  `git push origin refs/tasks/*:refs/tasks/*`

An explicit refspec on the command line overrides configured refspecs for that
invocation, so tsk's sync neither depends on nor disturbs the repo's
`remote.origin.fetch`. There is therefore nothing for `tsk init` to set up, and the
command is removed. `origin` is inherited from the project clone; syncing against a
different remote is a non-goal for the MVP (a `--remote` flag can be added later without
revisiting this decision).

## Alternatives considered

- **Persist the fetch refspec in git config (`tsk init`).** Rejected: mutates a shared
  repo's config and changes every contributor's `git fetch`, and reintroduces the silent
  empty-backlog failure as a mandatory setup step.
- **Fetch directly into `refs/tasks/*`** (`+refs/tasks/*:refs/tasks/*`). Rejected: works
  while refs are create-only but force-clobbers local task refs the instant Milestone B
  makes them mutable. We fetch into the `refs/remotes/origin/tasks/*` tracking namespace
  and adopt separately, which stays correct across B.

## Consequences

### Positive

- Zero footprint on the host repo's git config; every contributor's `git status`,
  `git fetch`, and setup are untouched — extends the "leaves no trace" property of
  ADR-0001.
- No required setup step, so the empty-backlog friction ADR-0001 named cannot occur
  through a skipped `tsk init`.
- Sync behaviour is independent of ambient config, so it is reproducible on any clone.

### Negative

- A plain `git fetch` still does not pull `refs/tasks/*` — only `tsk sync` does. The
  backlog stays invisible to bare git, as ADR-0001 already accepted.
- The remote is hard-defaulted to `origin`; a different remote needs a future flag.

## Relationship to ADR-0001

This does not supersede ADR-0001 — ops in custom refs stands. It refines ADR-0001's
"explicit refspec must be configured" consequence: tsk supplies the refspec itself per
invocation rather than pushing configuration onto users, removing the friction instead
of formalizing it.
