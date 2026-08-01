import json
import os
import subprocess
import time

from . import git
from . import ops
from .ops import Create, Op, SetBody, SetDeleted, SetStatus, SetTitle

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford Base32: no I, L, O, U

def _encode(value: int, length: int) -> str:
    """
    Render an integer as `length` Crockford Base32 chars, most-significant first.

    Args:
        value: the non-negative integer to encode.
        length: how many base-32 chars to emit (zero-padded on the left).

    Returns:
        The Base32 string.
    """
    chars = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))

def ulid() -> str:
    """
    Generate a ULID: a 26-char, lexicographically sortable, unique ID.

    Layout: 48-bit millisecond timestamp (high bits) + 80-bit randomness (low bits).

    Returns:
        The 26-char Crockford Base32 ULID.
    """
    timestamp = int(time.time() * 1000)              # 48 bits: ms since the epoch
    randomness = int.from_bytes(os.urandom(10))      # 80 bits: 10 random bytes
    value = (timestamp << 80) | randomness
    return _encode(value, 26)

def write_create(title: str) -> str:
    """
    Create a new task: build a create op, store it, and point a fresh ref at it.

    Args:
        title: the task's title.

    Returns:
        The new task's id (the ULID, also the ref suffix).
    """
    task_id = ulid()
    op = Create(id=task_id, lamport=1, title=title)
    blob = git.hash_object(ops.canonical(op))
    tree = git.mktree_with_blob(blob, "op")
    commit = git.commit_tree(tree, b"create")
    git.update_ref(f"refs/tasks/{task_id}", commit, "")
    return task_id

def _head_lamport(ref: str) -> int:
    """
    Read the highest lamport in a task's history.

    Every op is written with max + 1, so an op's lamport already exceeds
    everything behind it: the highest sits at the head, or — when the head is
    an op-less sync merge (ADR-0002) — at the nearest op commit on each side.

    Args:
        ref: a task ref, e.g. "refs/tasks/<ULID>".

    Returns:
        The highest lamport reachable from ref.
    """
    frontier = [git.rev_parse(ref)]
    highest = 0
    while frontier:
        commit = frontier.pop()
        try:
            blob_oid = git.rev_parse(f"{commit}:op")
        except subprocess.CalledProcessError:
            frontier.extend(git.parents(commit))  # op-less merge: look behind it
            continue
        highest = max(highest, json.loads(git.cat_file(blob_oid))["lamport"])
    return highest

def _next_lamport(task_id: str) -> int:
    """
    Pick the lamport for the next op on a task.

    Args:
        task_id: the task's id (the ref suffix).

    Returns:
        One past the highest lamport already in the task's history.
    """
    return _head_lamport(f"refs/tasks/{task_id}") + 1

def _append(op: Op) -> None:
    """
    Append an op to its task's ref.

    Args:
        op: the op to store; its `id` names the ref it lands on.
    """
    ref = f"refs/tasks/{op.id}"
    parent = git.rev_parse(ref)
    blob = git.hash_object(ops.canonical(op))
    tree = git.mktree_with_blob(blob, "op")
    commit = git.commit_tree(tree, ops.tag(op).encode(), parents=[parent])
    git.update_ref(ref, commit, parent)

def write_set_status(task_id: str, status: str) -> None:
    """
    Change a task's status: build a set_status op and append it to the task's ref.

    Args:
        task_id: the task's id (the ref suffix).
        status: the new status.
    """
    _append(SetStatus(id=task_id, lamport=_next_lamport(task_id), status=status))

def write_set_title(task_id: str, title: str) -> None:
    """
    Change a task's title: build a set_title op and append it to the task's ref.

    Args:
        task_id: the task's id (the ref suffix).
        title: the new title.
    """
    _append(SetTitle(id=task_id, lamport=_next_lamport(task_id), title=title))

def write_set_body(task_id: str, body: str) -> None:
    """
    Change a task's body: build a set_body op and append it to the task's ref.

    Args:
        task_id: the task's id (the ref suffix).
        body: the new body.
    """
    _append(SetBody(id=task_id, lamport=_next_lamport(task_id), body=body))

def write_set_deleted(task_id: str, deleted: bool) -> None:
    """
    Change a task's deleted flag: build a set_deleted op and append it to the
    task's ref.

    The ref itself is never removed, so a deleted task's history stays intact
    and can be restored by writing `deleted=False` later; deletion only hides
    the task from `ls`.

    Args:
        task_id: the task's id (the ref suffix).
        deleted: the new deleted flag.
    """
    _append(SetDeleted(id=task_id, lamport=_next_lamport(task_id), deleted=deleted))
