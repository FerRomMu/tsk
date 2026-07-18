# Implementation plan

> Living document, not an ADR. Edit it as milestones complete; delete it once the tool
> exists. The immutable *why* lives in `docs/adr/` — this is the *what next*.

**Next: Milestone A, step 1 — `git.py`.**

A git-native task backlog for a team on a shared remote. Ops stored under `refs/tasks/*`,
state derived by folding, sync through the central remote. Small and simple: four ops,
fold, sync. Nothing else.

## File layout

```
tsk/
  git.py     # subprocess wrapper over git plumbing
  op.py      # ULID, canonical JSON, op construction + write
  fold.py    # read refs → ops → sorted → Task state
  sync.py    # fetch, merge, push
  cli.py     # argparse entry point
  __main__.py
```

## Milestones

Built as a walking skeleton: thinnest slice that runs first, widen from there. Sync is
pulled forward and proven early on the smallest op set, because it is the novel and
failure-prone part.

**A — Create + list (local).**
Objects go in, state comes out. Establishes the plumbing wrapper, the write path, and the
read/fold path. Each task is its own ref, so nothing diverges yet.

**B — `set_status` + `tsk mv`.**
A second op type means a task's ref can grow past its first commit, so two clones can
diverge on the same task. This is the minimum needed to actually exercise a merge.

**C — Sync.**
- `tsk init` — configure the refspec `+refs/tasks/*:refs/remotes/origin/tasks/*`.
- `fetch`.
- Per task, compare local head to remote-tracking head: equal → skip; one ahead →
  fast-forward or push; diverged → empty-tree merge commit with two parents, adopted
  locally.
- Push, with a fetch→merge→push retry loop on non-fast-forward rejection.

At the end of C the full design is proven against two clones editing the same task.

**D — Remaining ops.**
`set_title`, `set_body`, `tsk edit`, `tsk show`, status validation that warns rather than
blocks. More op-writing on a spine that already works.

## Milestone A steps (one commit each)

1. `git.py` — `run(args, stdin=None)` plus thin helpers for the plumbing we need
   (`hash-object`, `mktree`, `commit-tree`, `update-ref`, `for-each-ref`, `rev-list`,
   `cat-file`). Never touches the working tree or index.
2. `op.py` — ULID generator (no stdlib ULID: 48-bit time + 80-bit random, Crockford
   base32, ~15 lines).
3. `op.py` — canonical serializer: NFC-normalize strings, then
   `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False)`, UTF-8, no
   trailing newline.
4. `op.py` — `write_create(title)`: op → blob → tree with one `op` entry → commit (no
   parent) → `update-ref refs/tasks/<ULID>`.
5. `fold.py` — fold one ref: `rev-list` it, read each commit's `op` blob, skip commits
   with no `op` entry, sort by `(lamport, blob_oid)`, apply ops → `Task`.
6. `fold.py` — enumerate `for-each-ref refs/tasks/*`, fold each → task list.
7. `cli.py` — `tsk new "<title>"` and `tsk ls`.

## Decisions

- **Lamport clock from the start.** Each op carries
  `lamport = 1 + max lamport over all ops reachable from the ref`. Required — concurrency
  is real once you sync.
- **`tsk init` is required.** It sets the fetch refspec; without it a clone silently sees
  an empty backlog.
- **ID ergonomics: unique ULID prefix.** Commands accept a unique prefix
  (`tsk mv 01J3 doing`) and warn on ambiguity. Full 26-char IDs always accepted.
