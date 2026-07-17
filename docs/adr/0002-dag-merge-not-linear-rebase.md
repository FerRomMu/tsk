# ADR-0002: DAG merge, not linear rebase

## Status

Accepted — 2026-07-17

## Context

Two clones edit the same backlog offline. Sync must reconcile them without losing any
op.

## Decision

Sync is: `fetch` → union of op sets → for each task, if the local and remote heads
have diverged, create a merge commit with both heads as parents and an empty tree →
normal push. Never force push. Never use `--force-with-lease`. The merge commit carries
no op; it carries topology only.

Extending the graph is the only write operation git offers. A commit can never know its
children, because a child's OID is a hash of content that includes the parent's OID —
the reverse pointer would be circular and non-computable. Append-only is therefore not
a policy we chose to follow; it is the only thing git permits.

## Alternatives considered

**Linear rebase**, rejected. Take the union of ops, sort by `(lamport, blob_oid)`,
rewrite the entire chain from scratch, `update-ref`, and push with `--force-with-lease`.
This is what git-bug did before version 0.8.

Four reasons for rejection:

1. **Force push is not ours to allow.** Rewriting produces a non-fast-forward push,
   which requires force push. `receive.denyNonFastForwards` is a server-side setting.
   If it is enabled, there is no client-side workaround — the server rejects the push
   and never looks at the lease. The tool's viability would depend on a configuration
   we do not control, and we would discover the problem on rollout day.

2. **The lease silently degrades to a plain force.** `--force-with-lease` without an
   explicit `=<oid>` uses the remote-tracking ref as the expected value. Our refspec
   mapping (`refs/tasks/*` → `refs/remotes/origin/tasks/*`) is not the one git assumes,
   and any background fetch updates the tracking ref, so the expected value silently
   becomes the current value and the check passes trivially. The protection degrades to
   a plain `--force` with no warning.

3. **Silent data loss across clones.** If A pushes op X and B then force-pushes, X
   becomes unreachable on the server. A third clone C fetching for the first time never
   receives X, because fetch only transfers objects reachable from the refs the refspec
   requested — X never crosses the wire. Server-side gc then deletes it. Bare repos have
   no reflog by default, so there is no safety net. The loss is undetectable: git has no
   concept of "objects that should be here", so every repo believes it has everything.
   Our union merge would self-heal this only if A syncs again — if A's disk dies, A
   re-clones, or A leaves the team, X is gone for the collective, and I3 says nothing
   about what happens when the op sets differ.

4. **Prior art abandoned it.** git-bug spent a major version migrating away from this
   model. It worked on star topology and broke on anything else.

The DAG is in fact the simpler option, not the advanced one. Because the total order is
derived from `(lamport, blob_oid)`, the chain's topology is never read — the fold sorts
everything before looking at anything. Rewriting the chain was pure wasted work that
additionally forced the force push. The DAG does less.

### Alternative 2, rejected: per-replica refs

Each clone appends only to its own ref, `refs/tasks/<ULID>/<replica-id>`, containing
only that replica's own ops. A ref with a single writer cannot diverge, so every push is
trivially fast-forward: no merge commit, no empty-tree topology object, no retry loop.
State is the fold over the union of all replicas' chains — which is what we already do,
so the read path is conceptually unchanged. This is a standard op-based CRDT technique
and several git-CRDT experiments run exactly this way.

This is not rejected on safety grounds. It is exactly as safe as merge commits:
uncontended refs, always fast-forward, no force push, no orphans possible. Every argument
above against linear rebase applies equally in per-replica's favour. It is also simpler
than what we chose, not more complex, and it requires no consensus. It is not worse in
every respect — on most axes it is better.

It is rejected on ref growth alone:

- Ref count becomes O(tasks × replicas), and "replicas" is not the team size — it is
  every clone that ever touched a task. The replica-id must be per-clone, not per-person:
  one person working from two machines is two replicas, because those machines write
  independently and would otherwise diverge on a shared ref, which reintroduces the merge
  we were trying to avoid. So the count includes every new laptop, every re-clone after a
  disk failure, every CI runner, every throwaway clone.

- These refs cannot be deleted. A dead replica's ref is not garbage — its ops are real
  data. Deleting it would require knowing that every participant has already seen those
  ops, which is consensus, which requires knowing who "everyone" is. The system has no
  membership concept: anyone can clone and show up six months later with old ops. This is
  the same wall as log compaction, and per-replica makes it worse rather than better,
  because it creates more refs that cannot be reclaimed.

- Realistic estimate: five developers over three years with hardware refresh is roughly
  twenty replicas — twenty times the refs, permanently, growing monotonically, with no
  path to reclaim.

A merge commit is ref compaction. We pay one object per sync and in exchange the ref
namespace stays O(tasks), flat, forever. It is also the only compaction available to us
without consensus, because a merge commit does not assert that anyone has seen anything —
it only asserts reachability, which is a local, verifiable fact.

Two further costs:

- Read path: `tsk list` already costs O(tasks) subprocesses and that is the known
  bottleneck. Per-replica multiplies it by the replica count on the hot path — 500 tasks
  across 5 replicas is roughly 7500 subprocesses per list.
- Replica identity is an explicit non-goal, and identity is precisely where git-bug's
  complexity grew from.

If this were a product rather than a learning exercise, per-replica would be competitive.
The deciding argument is ref growth, not elegance. Revisit if ref count ever stops being
expensive — for example if the reftable backend makes large ref stores cheap — or if
merge commits turn out to cost more than projected.

## Consequences

### Positive

- A merge commit makes everything reachable from either parent reachable from itself, so
  orphaned objects cannot be produced and the scenario in rejection reason 3 has nowhere
  to occur.
- Works on any topology and against any server configuration.
- Append-only becomes true at every layer, which removes the caveat that invariant I2
  previously carried.
- Commit OIDs become permanently stable.

### Negative

- Merge commits accumulate and the DAG becomes bushy.
- Chain order no longer equals total order. This is harmless — we always sort before
  folding — but it means the chain must never be read in its stored order.
- The push is not fast-forward by construction. The merge commit is a descendant of the
  remote head *we fetched*, not of the head the server holds at push time. If someone
  pushes between our fetch and our push, the push is rejected as non-fast-forward and we
  loop: fetch → merge → push. Implementers must expect this retry loop and must not
  assume first-try success. What survives the correction is the actual point: the
  rejection is git's native fast-forward check, not a protection someone has to remember
  to configure. It fails closed, no data can be lost, and retrying is the correct
  response. That is the difference from force push — not that the push never fails.
- The compare-and-swap is per-ref, so the blast radius of a collision is one task; two
  people syncing different tasks never contend. But without `--atomic`, a multi-ref push
  is partial — some refs land, some are rejected — leaving the clone half-synced.
  Recoverable by running sync again, but implementers should know it.

## Note for implementers

We never invoke `git merge`. Merge commits are built with `commit-tree` and two `-p`
flags. Git's three-way merge machinery never runs — see ADR-0003 for why it could not
work here even if we wanted it.
