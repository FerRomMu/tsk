import subprocess

from . import git
from .git_exceptions import PushRejectedError

REMOTE = "origin"
FETCH_REFSPEC = "+refs/tasks/*:refs/remotes/origin/tasks/*"
PUSH_REFSPEC = "refs/tasks/*:refs/tasks/*"
PUSH_MAX_ATTEMPTS = 5

def prune(task_id: str) -> None:
    """
    Hard-delete a task's ref locally.

    The task ref itself is destroyed, but its tracking ref (if the task has
    ever been synced) is bumped to match first, so a later `pull` can tell
    this task was deliberately pruned — as opposed to simply never having
    been fetched — and knows what oid to try deleting on the remote (see
    `pull`). A task that was never synced has no tracking ref to bump, so it
    is just erased locally with nothing left to propagate: no trace of it
    was ever shared.

    Args:
        task_id: the task's id (the ref suffix).
    """
    ref = f"refs/tasks/{task_id}"
    oid = git.rev_parse(ref)
    git.delete_ref(ref, oid)

    tracking_ref = f"refs/remotes/origin/tasks/{task_id}"
    try:
        git.rev_parse(tracking_ref)
    except subprocess.CalledProcessError:
        return  # never synced; nothing to propagate
    git.update_ref(tracking_ref, oid)

def pull() -> None:
    """
    Fetch task refs from the remote and reconcile local refs against them.

    Fetches refs/tasks/* into the tracking namespace, then for every task on
    the remote reconciles the local ref by reachability:

    - pruned (see below)    -> try to delete it on the remote too
    - missing locally      -> adopt the remote head
    - identical            -> nothing to do
    - remote strictly ahead -> fast-forward to it
    - local strictly ahead  -> leave it for push to send
    - diverged              -> empty-tree merge commit over both heads (ADR-0002)

    Diverged heads are joined with a two-parent merge commit whose tree is empty:
    it carries topology only, no op, so fold skips it. This makes every op from
    either side reachable from the new local head; the fold's (lamport, blob_oid)
    order — not chain topology — decides the resulting state.

    A task is "pruned" when its tracking ref already existed before this
    fetch but it now has no local ref — the only way that happens is
    `sync.prune()`. For those, delete the remote ref too, gated on the
    remote still being at the oid we last saw (a real compare-and-swap: see
    `git.push_delete`). If the remote has since moved — someone pushed new
    ops after the prune — the delete is refused, and the pruned oid is fed
    into the normal reconciliation above as a stand-in for the missing local
    ref, so the task is restored, merged with whatever's new. Losing that
    race just means the prune didn't happen; nothing is silently discarded.
    """
    prior_tracking = {
        ref.rsplit("/", 1)[1]: oid
        for ref, oid in git.for_each_ref("refs/remotes/origin/tasks/*")
    }
    git.fetch(REMOTE, FETCH_REFSPEC)

    local = {
        ref.rsplit("/", 1)[1]: oid for ref, oid in git.for_each_ref("refs/tasks/*")
    }
    for ref, remote_oid in git.for_each_ref("refs/remotes/origin/tasks/*"):
        ulid = ref.rsplit("/", 1)[1]
        task_ref = f"refs/tasks/{ulid}"
        local_oid = local.get(ulid)
        pruned = local_oid is None and ulid in prior_tracking

        if pruned:
            expected = prior_tracking[ulid]
            if git.push_delete(REMOTE, task_ref, expected):
                git.delete_ref(ref, expected)  # tracking ref is now stale
                continue
            print(f"tsk: could not prune {ulid}: the remote changed since it "
                  f"was pruned; restoring it, merged with the newer state")
            local_oid = expected  # fall through, treated as the missing local ref

        # Below, `continue` means "the local ref is already correct as-is" —
        # true when it really exists on disk, false when local_oid is only a
        # pruned stand-in (the ref itself is gone), so those branches must
        # still write it back whenever `pruned`.
        if local_oid is None:
            git.update_ref(task_ref, remote_oid)  # adopt missing
        elif local_oid == remote_oid:
            if pruned:
                git.update_ref(task_ref, remote_oid)  # restore: nothing raced us
            continue  # already in sync
        elif git.is_ancestor(local_oid, remote_oid):
            git.update_ref(task_ref, remote_oid)  # fast-forward
        elif git.is_ancestor(remote_oid, local_oid):
            if pruned:
                git.update_ref(task_ref, local_oid)  # restore at our pruned oid
            continue  # local strictly ahead — push will send it
        else:
            merge = git.commit_tree(
                git.empty_tree(), b"merge", parents=[local_oid, remote_oid]
            )
            git.update_ref(task_ref, merge)  # join diverged heads

def push() -> None:
    """
    Push all local task refs to the remote.

    Sends refs/tasks/* to the identically-named refs on the remote.
    """
    git.push(REMOTE, PUSH_REFSPEC)

def run() -> None:
    """
    Synchronize local tasks with the remote: reconcile, then push.

    Pulls once to reconcile, then pushes. If the remote moved in between, the
    push is rejected non-fast-forward; pulls again to re-reconcile and retry,
    bounded by PUSH_MAX_ATTEMPTS. The final rejection propagates.
    """
    pull()
    for attempt in range(PUSH_MAX_ATTEMPTS):
        try:
            push()
            return
        except PushRejectedError:
            if attempt == PUSH_MAX_ATTEMPTS - 1:
                raise
            pull()