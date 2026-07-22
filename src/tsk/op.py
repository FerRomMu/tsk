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
    tree = git.mktree([("100644", "blob", blob, "op")])
    commit = git.commit_tree(tree, b"create")
    git.update_ref(f"refs/tasks/{task_id}", commit, "")
    return task_id

def _max_lamport(ref: str) -> int:
    """
    Find the highest lamport value among the ops reachable from a ref.

    Args:
        ref: a task ref, e.g. "refs/tasks/<ULID>".

    Returns:
        The highest lamport value found, or 0 if the ref has no ops.
    """
    lamport = 0
    for commit in git.rev_list(ref):
        try:
            blob_oid = git.rev_parse(f"{commit}:op")
        except subprocess.CalledProcessError:
            continue  # commit with no op payload (e.g. a merge)
        op = json.loads(git.cat_file(blob_oid))
        lamport = max(lamport, op["lamport"])
    return lamport

def write_set_status(task_id: str, status: str) -> None:
    """
    Change a task's status: build a set_status op and append it to the task's ref.

    Args:
        task_id: the task's id (the ref suffix).
        status: the new status.
    """
    ref = f"refs/tasks/{task_id}"
    parent = git.rev_parse(ref)
    op = {
        "op": "set_status",
        "id": task_id,
        "lamport": _max_lamport(ref) + 1,
        "status": status,
    }
    blob = git.hash_object(canonical(op))
    tree = git.mktree([("100644", "blob", blob, "op")])
    commit = git.commit_tree(tree, b"set_status", parents=[parent])
    git.update_ref(ref, commit, parent)
