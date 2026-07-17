# ADR-0001: Ops in custom refs

## Status

Accepted — 2026-07-17

## Context

The backlog must live inside the repository, so that cloning the project clones the
backlog. It must travel with a clone, sync over git, and work offline. Two storage
strategies were available: files committed in the working tree, or git objects stored
under a private ref namespace.

## Decision

Store ops as git objects under `refs/tasks/<ULID>`, outside `refs/heads/`. The working
tree is never touched — no tsk file is ever written to a checkout. Enumeration of the
backlog is done with `for-each-ref` over `refs/tasks/*`.

## Alternatives considered

- **(a) Markdown or JSON files committed in the working tree.** This is the approach
  taken by Backlog.md and ghist. The backlog would be plain files, versioned like any
  other source.
- **(b) An orphan branch.** This is the approach taken by ticgit — a detached branch
  holding the task data, kept out of the mainline history.

Prior art for the chosen approach — task or metadata storage under a private ref
namespace — is git-bug, `git notes` (`refs/notes/`), and Gerrit (`refs/meta/config`).

## Consequences

### Positive

- Git's textual merge never runs on task data, so conflict markers in the backlog are
  structurally impossible.
- `git status` stays clean permanently (I1) — the backlog leaves no trace in the
  working tree.
- No index file is needed; all enumeration derives from the refs (I4).
- The backlog travels with a normal clone, satisfying the core requirement.

### Negative

- We lose grep, diff, blame, and pull-request review of the backlog — the exact things
  files would have given us for free. Nothing in the backlog can be read without the
  binary installed.
- `refs/tasks/*` is not fetched by a default `git fetch`. An explicit refspec must be
  configured, and if a team member skips it they see an empty backlog with no
  indication why. This is the tool's primary adoption friction.
- Reversing this decision requires a data migration, not a code change.
