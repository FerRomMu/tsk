import json
import os
import subprocess
import time
import unicodedata

from . import git

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

def canonical(op: dict) -> bytes:
    """
    Serialize an op to its canonical byte form for hashing.

    Deterministic across machines: NFC-normalized string values, sorted keys,
    no incidental whitespace, UTF-8, no trailing newline.

    Args:
        op: the op as a flat dict (str keys; str or int values).

    Returns:
        The canonical UTF-8 bytes.
    """
    normalized = {
        key: unicodedata.normalize("NFC", value) if isinstance(value, str) else value
        for key, value in op.items()
    }
    text = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode()

def write_create(title: str) -> str:
    """
    Create a new task: build a create op, store it, and point a fresh ref at it.

    Args:
        title: the task's title.

    Returns:
        The new task's id (the ULID, also the ref suffix).
    """
    task_id = ulid()
    op = {"op": "create", "id": task_id, "lamport": 1, "title": title}
    blob = git.hash_object(canonical(op))
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

def _write_set(task_id: str, field: str, value: str | bool) -> None:
    """
    Append a set_<field> op to a task's ref.

    Args:
        task_id: the task's id (the ref suffix).
        field: the field being set; also names the op ("set_" + field).
        value: the field's new value.
    """
    op_name = f"set_{field}"
    ref = f"refs/tasks/{task_id}"
    parent = git.rev_parse(ref)
    op = {
        "op": op_name,
        "id": task_id,
        "lamport": _head_lamport(ref) + 1,
        field: value,
    }
    blob = git.hash_object(canonical(op))
    tree = git.mktree_with_blob(blob, "op")
    commit = git.commit_tree(tree, op_name.encode(), parents=[parent])
    git.update_ref(ref, commit, parent)

def write_set_status(task_id: str, status: str) -> None:
    """
    Change a task's status: build a set_status op and append it to the task's ref.

    Args:
        task_id: the task's id (the ref suffix).
        status: the new status.
    """
    _write_set(task_id, "status", status)

def write_set_title(task_id: str, title: str) -> None:
    """
    Change a task's title: build a set_title op and append it to the task's ref.

    Args:
        task_id: the task's id (the ref suffix).
        title: the new title.
    """
    _write_set(task_id, "title", title)

def write_set_body(task_id: str, body: str) -> None:
    """
    Change a task's body: build a set_body op and append it to the task's ref.

    Args:
        task_id: the task's id (the ref suffix).
        body: the new body.
    """
    _write_set(task_id, "body", body)

def write_set_deleted(task_id: str, deleted: bool) -> None:
    """
    Change a task's deleted flag: build a set_deleted op and append it to the
    task's ref.

    The ref itself is untouched here, so a deleted task's history stays
    intact and can be restored by writing `deleted=False` later; deletion
    only hides the task from `ls`. Actually erasing the ref is a separate,
    explicit step — see `sync.prune`.

    Args:
        task_id: the task's id (the ref suffix).
        deleted: the new deleted flag.
    """
    _write_set(task_id, "deleted", deleted)
