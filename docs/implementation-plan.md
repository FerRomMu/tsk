# Implementation plan

> 🤖 Generated with Claude (Claude Code). Review critically before relying on it.

> Living document, not an ADR. Edit it as milestones complete; delete it once the tool
> exists. The immutable *why* lives in `docs/adr/` — this is the *what next*.

**Now: Milestone C-lite — sync on the create-only op set. A is complete; C is pulled ahead of B.**

A git-native task backlog for a team on a shared remote. Ops stored under `refs/tasks/*`,
state derived by folding, sync through the central remote. Small and simple: four ops,
fold, sync. Nothing else.

## File layout

```
tsk/
  git.py     # subprocess wrapper over git plumbing
  op.py      # ULID, canonical JSON, op construction + write
  fold.py    # read refs → ops → sorted → Task state
  sync.py    # fetch + adopt, push (merge/retry deferred to B)
  cli.py     # argparse entry point
  __main__.py
```

## Milestones

Built as a walking skeleton: thinnest slice that runs first, widen from there. Sync is
pulled forward and proven early on the smallest op set, because it is the novel and
failure-prone part.

Build order is **A → C-lite → B → D**. Sync ships first on the create-only op set
(C-lite): create-only refs are write-once and cannot diverge, so the risky parts — merge
commits and the push retry loop — are deferred until B makes refs mutable. See ADR-0002
for that eventual design.

**A — Create + list (local).**
Objects go in, state comes out. Establishes the plumbing wrapper, the write path, and the
read/fold path. Each task is its own ref, so nothing diverges yet.

**B — `set_status` + `tsk mv`.**
A second op type means a task's ref can grow past its first commit, so two clones can
diverge on the same task. This is the minimum needed to actually exercise a merge. Refs
become mutable here, so the deferred merge commit and push retry loop (ADR-0002) become
mandatory before syncing is safe again.

**C (C-lite) — Sync.**
Built on the create-only op set. Task refs are write-once, globally-unique ULIDs, so two
clones only ever ADD distinct refs — no task ref diverges, no push is non-fast-forward.
The tool mutates no git config and adds no remote; it passes explicit refspecs and
defaults to `origin` (the remote the project was cloned from — the backlog lives in the
project's own repo, so origin is inherited). No `tsk init`.

- **pull** — `fetch` with an explicit refspec into the tracking namespace
  (`+refs/tasks/*:refs/remotes/origin/tasks/*`), then adopt every ULID present in the
  tracking refs but missing locally via `update-ref`. Equal refs → skip.
- **push** — `push refs/tasks/*:refs/tasks/*`. Cannot be rejected while refs are
  create-only.
- **`tsk sync`** — pull then push.

Deferred to B, dead until refs are mutable: the empty-tree merge commit for diverged task
heads and the fetch→merge→push retry loop on non-fast-forward rejection — the full
ADR-0002 design. At the end of B the design is proven against two clones editing the same
task.

**D — Remaining ops.**
`set_title`, `set_body`, `tsk edit`, `tsk show`, status validation that warns rather than
blocks. More op-writing on a spine that already works.

## Milestone A steps (one commit each) — ✓ complete

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

## Milestone C-lite steps (one commit each)

1. `git.py` — `fetch(remote, refspec)`. ✓
2. `git.py` — `push(remote, refspec)`. ✓
3. `sync.py` — `pull()`: fetch the tracking refspec, then `update-ref`-adopt every task
   ref present in `refs/remotes/origin/tasks/*` but missing from `refs/tasks/*`.
4. `sync.py` — `push()`: push `refs/tasks/*:refs/tasks/*` to origin.
5. `cli.py` — `tsk sync`: pull then push.

## Decisions

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
