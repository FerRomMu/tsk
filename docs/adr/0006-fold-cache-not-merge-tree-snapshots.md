# ADR-0006: Fold cache, not merge-tree snapshots

## Status

Accepted — 2026-07-30

## Context

Reading a task's state means folding: `rev-list` the ref, read each commit's `op` blob,
sort the ops by `(lamport, blob_oid)`, and apply them. The cost grows with a task's
history — every read re-walks and re-folds every op the task has ever accumulated. For a
task that lives for years this is pure repeated work: the same ops fold to the same state
every time.

There is a natural checkpoint already in the graph. A sync merge (ADR-0002) is a causal
synchronisation point: everything reachable from a merge `M` is causally *before* anything
appended after it. With the lamport clock computed as `1 + max lamport reachable`
(`op._head_lamport`), that causal order is reflected in the total order — every op appended
after `M` carries a lamport strictly greater than every op in the reachable set `S_M`.
Therefore `fold(S_M)` is a valid *prefix* of the fold, and the ops after `M` are
strictly-ordered deltas on top of it. The state at any head is
`apply(fold(nearest_merge_ancestor), ops_after_it)` — we do not have to start from zero.

That memoised prefix has to live somewhere. This ADR is about where.

Two properties of the current op set sharpen the picture. Every op is `set_<field>` — a
last-writer-wins register — so the folded value of a field is simply the value of its
highest-`(lamport, blob_oid)` op. An op that arrives with a *lower* key interleaves into
the middle of the order and is overwritten by everything after it; it cannot change the
result. This makes a checkpoint unusually robust: it is invalidated only by an op that
sorts *after* the checkpoint's frontier, never by a late low-lamport straggler. (This holds
only while every op is LWW; a future non-LWW op — a counter, a text-CRDT body — would make
order matter again and must revisit this.)

## Decision

Memoise the fold in a **local, external, disposable cache**, keyed by the commit OID being
folded.

- **Key: the commit OID.** Commit OIDs are permanently stable (ADR-0002, "commit OIDs
  become permanently stable"), so the head OID is a content-addressed key with no
  invalidation logic to get wrong: if the ref head is already in the cache, return the
  stored state; otherwise fold and store it. When the ref advances, the new head is a new
  key — a miss — and the fold recomputes.
- **Checkpoint at merges.** The cache is most valuable at merge OIDs, because a merge's
  entry is reused by every future head built on top of it: `fold(head)` folds only the ops
  between the nearest cached ancestor and the head, not the whole history.
- **Storage: outside the object database.** The cache lives under `.git/` (e.g.
  `.git/tsk/fold-cache`), is never committed, and is never pushed. It is a pure derivation
  of the refs: safe to delete, rebuilt on demand. It does not violate ADR-0001's "state
  derives from refs" — it *is* that derivation, memoised, not a second source of truth.

## Alternatives considered

### Rejected: snapshot in the merge commit's tree

Instead of an empty tree, a sync merge would carry the materialised task state as its tree
— `git diff`/`git log` would show it, and every clone would inherit the snapshot for free
without folding.

Rejected. It puts *derived, rebuildable* data into *immutable, shared* history, and reopens
two accepted decisions: ADR-0002 ("the merge commit carries no op; it carries topology
only") and ADR-0003 ("our commits hold a loose delta — a snapshot tree is exactly the
convention we chose to violate").

The failure is concrete, and this repository already lived the setup for it: the `body`
field was added after `title` and `status` existed.

- A clone still running the old binary — a teammate who did not update, a CI runner, a
  stale checkout — syncs a diverged task and bakes a merge whose tree snapshots
  `{title, status}`, with no `body`, because its binary has no concept of one.
- That merge is pushed. It is now in the permanent history of every clone, and history is
  immutable — it cannot be corrected, only layered over with more merges.
- A newer client that trusts the snapshot in that merge reads the task with no body, even
  though the `set_body` op is sitting healthy in the graph. The baked derived state is
  lying, forever, to everyone.

The structural root: a baked snapshot is only valid *as of its own merge*. To know whether
it is still current you must check for newer ops — the very traversal the snapshot was
meant to avoid — and under concurrency there are several competing "latest" merges (each
replica builds its own, with a distinct OID from parent order and committer date), so there
is no single place to read "current state" from. Everything unique to this option is the
sharing of the snapshot across clones, and that sharing is exactly what turns a stale or
version-mismatched value into permanent, collective corruption.

A local cache has none of this: it is private, versioned with the binary that wrote it,
keyed on the head OID the reader already holds, and thrown away and recomputed on any doubt.
A wrong entry is a local performance blip that self-heals, never shared truth.

### Rejected for now: no cache (status quo)

Fold every read from scratch. Correct and simple, and fine while task histories are short.
Revisit — i.e. adopt this ADR's cache — when per-task history length becomes a measured
read cost.

## Consequences

### Positive

- Read cost for a deep task drops from "fold all ops" to "fold the ops since the nearest
  cached checkpoint".
- ADR-0001, -0002, -0003, -0004 are all untouched: the object store stays a pure op log,
  merges stay empty-tree topology, nothing derived is committed or pushed.
- The cache is self-healing: delete it, change the binary, or hit any inconsistency, and the
  next read rebuilds it from the refs.

### Negative

- It is the first piece of local state outside the refs. Softened by being a *derivation*
  cache — rederivable and disposable — rather than a source of truth, but it is still a file
  to manage, locate, and (if ever corrupted) invalidate.
- It does **not** address the known bottleneck of `tsk ls`, which is `O(tasks)` subprocess
  spawns (ADR-0002), not per-task fold depth. That wants `cat-file --batch`, an orthogonal
  change. This cache helps deep histories, not wide backlogs.

### Prerequisite

Relies on the lamport clock being `1 + max lamport reachable` so that a merge is a true
total-order barrier. This is already the case on `master` via `op._head_lamport`, which
walks behind op-less merges to take the maximum across both sides.
