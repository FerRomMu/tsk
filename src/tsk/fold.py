import json
import subprocess

from . import git
from .models import Task


def fold_all() -> list[Task]:
    """
    Fold every task ref into its current state.

    Returns:
        One Task per ref under refs/tasks/*, in creation order
        (for-each-ref sorts by refname, and refnames are time-sortable ULIDs).
    """
    return [
        fold_ref(oid) for _, oid in git.for_each_ref("refs/tasks/*")
    ]

def fold_ref(ref: str) -> Task:
    """
    Fold one task ref into its current state.

    Walk every commit reachable from the ref, read each commit's `op`
    blob (skipping any commit that carries none), order the ops by
    (lamport, blob_oid), and apply them into a Task.

    Args:
        ref: a task ref or its OID, e.g. "refs/tasks/<ULID>".

    Returns:
        The Task the ops fold to.
    """
    ops = []
    for commit in git.rev_list(ref):
        try:
            blob_oid = git.rev_parse(f"{commit}:op")
        except subprocess.CalledProcessError:
            continue  # commit with no op payload (e.g. a merge)
        op = json.loads(git.cat_file(blob_oid))
        ops.append((op["lamport"], blob_oid, op))

    task = None
    for _, _, op in sorted(ops, key=lambda row: (row[0], row[1])):
        if op["op"] == "create":
            task = Task(id=op["id"], title=op["title"])
        elif op["op"] == "set_status":
            task.status = op["status"]
    return task


