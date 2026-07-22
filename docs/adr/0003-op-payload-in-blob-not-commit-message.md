# ADR-0003: Op payload in blob+tree, not in the commit message

> 🤖 Generated with Claude (Claude Code). Review critically before relying on it.

## Status

Accepted — 2026-07-17

## Context

Each op must be stored as a git object.

## Decision

Serialize the op to JSON → write it as a blob → build a tree with a single entry named
`op` pointing at that blob → build a commit with that tree. The commit message is
irrelevant and is never parsed.

## Alternatives considered

Put the JSON in the commit message and use the empty tree
(`4b825dc642cb6eb9a060e54bf8d69288fbee4904`). This is two plumbing commands instead of
four. Rejected because the blob is what ADR-0004 depends on: a first-class object with a
content-only OID. Folding the payload into the commit message would make the op's
identity an accident of how the commit was packaged.

## Consequences

### Positive

- The op has a stable identity independent of packaging.
- The payload is not constrained by commit-message conventions around size or encoding.

### Negative

- One extra object per op.

## Note: we violate a git convention on purpose

A commit's tree is supposed to be the complete state of the project at that point; ours
holds a loose delta — a single op. Nothing in git enforces this and git does not care,
but it means `git diff`, `git merge`, and `git log -p` are meaningless over
`refs/tasks/*`. We are using commits as transport for a DAG, not as snapshots. git-bug
does the same thing.

This is also why `git merge` could never work on our refs even if we wanted it to.
Git's three-way merge asks, per path: is this side equal to the merge base? If yes, that
side did not change and the other side wins. Our commits have exactly one path (`op`),
and both sides always changed it to something different. Every merge would conflict,
every time, without exception. Git needs the merge base because with two states it
cannot tell who changed what. We do not have that problem: our ops *are* the changes —
direction is already encoded in them — so there is nothing to infer and nothing to
compare against. This is why `tsk` never calls `merge-base`.

Merge commits (ADR-0002) use the empty tree and carry no `op` entry. Readers must skip
any commit that has no `op` entry in its tree.
