---
name: tsk
description: >-
  Operate the `tsk` git-native task backlog that lives in this repository. Use
  whenever the user wants to create, list, inspect, edit, move (change status
  of), or sync tasks — anything about "the backlog", "the tasks", "tsk", or
  work items tracked under `refs/tasks/*`. Covers the full command surface and
  the id-prefix, status, and sync conventions an agent needs to drive the tool
  correctly.
---

# tsk

`tsk` is a git-native task backlog: a small CLI over a shared git remote. There
is no database and no server. Every task is a chain of append-only *ops* stored
as commits under its own ref (`refs/tasks/<ULID>`), and the current state of a
task is *folded* (replayed) from those ops on read. Sync is plain `git`
fetch/push through the project's own `origin`.

You don't need the internals to use it — the commands below are the whole
interface — but two facts shape everything: **the working tree is never
touched** (`git status` stays clean; the backlog lives entirely in refs), and
**nothing is shared until you `tsk sync`** (a normal `git fetch`/`git pull` does
*not* transfer `refs/tasks/*`).

## Running it

Inside this repo:

```
uv run tsk <command> ...
```

If the package is installed on PATH, just `tsk <command> ...`. All examples
below omit the `uv run` prefix for brevity.

## Commands

### `tsk new "<title>"`
Create a task. Prints the new task's 26-char ULID (also its ref name). Quote
the title so the shell keeps it as one argument.

```
$ tsk new "write the release notes"
01J8Z3K9R7Q2VN4YB0C5MHT6DA
```

### `tsk ls`
List every task, one per line, in creation order (ULIDs sort by time). Shows
id, title, status, and body.

```
$ tsk ls
Task(id='01J8Z3K9R7Q2VN4YB0C5MHT6DA', title='write the release notes', status='todo', body='')
```

### `tsk show <id>`
Print one task's full detail — every field, rendered for reading rather than as
a one-line repr. Use it when a task's body is long or you want to confirm an
edit landed.

```
$ tsk show 01J8Z3
id:     01J8Z3K9R7Q2VN4YB0C5MHT6DA
title:  write the release notes
status: doing
body:   cover the sync retry-loop fix and the new edit command
```

### `tsk mv <id> <status>`
Change a task's status (move it across the board — e.g. `todo` → `doing` →
`done`).

```
$ tsk mv 01J8Z3 doing
```

Statuses are free-form strings; the tool **warns** on an unrecognized status
rather than blocking it, so a typo is visible but never fatal.

### `tsk edit <id> [--title "<title>"] [--body "<body>"]`
Change a task's title and/or body. At least one flag is required; passing both
edits both in one invocation. Omitted fields are left unchanged.

```
$ tsk edit 01J8Z3 --title "write v0.2 release notes"
$ tsk edit 01J8Z3 --body "cover the sync retry-loop fix"
$ tsk edit 01J8Z3 --title "release notes" --body "short and to the point"
```

### `tsk sync`
Reconcile the local backlog with `origin`: fetch, adopt/merge remote task
changes, then push. Reports what changed — which tasks a pull created,
advanced, or merged — instead of syncing silently.

```
$ tsk sync
pulled:  01J8Z3 (advanced), 01J91A (new)
pushed:  01J8ZP
```

`tsk sync` is the **only** command that moves tasks between clones. A teammate's
`tsk new`/`tsk edit`/`tsk mv` is invisible to you until one of you syncs. The
push is git's native fast-forward check; if someone pushed between your fetch
and your push, `tsk sync` loops (fetch → merge → push) until it lands — expect
that, it is normal and loses nothing.

## Referring to tasks: id prefixes

Every command that takes an `<id>` accepts a **unique prefix** of the ULID, not
just the full 26 chars:

```
$ tsk mv 01J8Z3 done     # fine, as long as 01J8Z3 matches exactly one task
```

If a prefix matches more than one task, the command refuses and lists the
candidates — lengthen the prefix. The full ULID always works. When scripting or
when a task set may grow, prefer the full id from `tsk new`/`tsk ls`.

## Working conventions (for agents)

- **After creating or editing, verify with `tsk ls` or `tsk show`.** Edits fold
  in immediately locally; a quick read confirms the change before you move on.
- **Sync at boundaries, not constantly.** Pull with `tsk sync` before you start
  a batch of task work so you're acting on current state, and again after, to
  publish. Don't sync after every single op.
- **Never hand-edit `refs/tasks/*` or run `git` against the backlog directly.**
  Ops must go through `tsk` so they get a correct lamport clock and canonical
  serialization; a raw git write will fold inconsistently across clones.
- **Quote titles and bodies.** They are single arguments; unquoted shell
  splitting will silently truncate them.
- **A clean `git status` is expected.** tsk writes nothing to the working tree,
  so task changes never show up as file diffs — that's by design, not a bug.

## Why it's built this way

The reasoning behind the ops-in-refs, fold-on-read, and DAG-merge design lives
in the Architecture Decision Records under `docs/adr/`. Read those if you need
the *why*; for using the tool, the commands above are enough.
