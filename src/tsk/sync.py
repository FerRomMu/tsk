from . import git

REMOTE = "origin"
FETCH_REFSPEC = "+refs/tasks/*:refs/remotes/origin/tasks/*"
PUSH_REFSPEC = "refs/tasks/*:refs/tasks/*"

def pull() -> None:
    """
    Fetch task refs from the remote and reconcile local refs against them.

    Fetches refs/tasks/* into the tracking namespace, then for every task on
    the remote reconciles the local ref by reachability:

    - missing locally      -> adopt the remote head
    - identical            -> nothing to do
    - remote strictly ahead -> fast-forward to it
    - local strictly ahead  -> leave it for push to send
    - diverged              -> empty-tree merge commit over both heads (ADR-0002)

    Diverged heads are joined with a two-parent merge commit whose tree is empty:
    it carries topology only, no op, so fold skips it. This makes every op from
    either side reachable from the new local head; the fold's (lamport, blob_oid)
    order — not chain topology — decides the resulting state.

    NOTE: The merge commit descends from the remote head we just fetched, not
    from whatever the server holds at push time, so the subsequent push can still
    be rejected non-fast-forward if someone pushed in between. The fetch->merge->
    push retry loop that closes that window is deferred (see docs/deferred.md).
    """
    git.fetch(REMOTE, FETCH_REFSPEC)

    local = {
        ref.rsplit("/", 1)[1]: oid for ref, oid in git.for_each_ref("refs/tasks/*")
    }
    for ref, remote_oid in git.for_each_ref("refs/remotes/origin/tasks/*"):
        ulid = ref.rsplit("/", 1)[1]
        local_oid = local.get(ulid)
        if local_oid is None:
            git.update_ref(f"refs/tasks/{ulid}", remote_oid)  # adopt missing
        elif local_oid == remote_oid:
            continue  # already in sync
        elif git.is_ancestor(local_oid, remote_oid):
            git.update_ref(f"refs/tasks/{ulid}", remote_oid)  # fast-forward
        elif git.is_ancestor(remote_oid, local_oid):
            continue  # local strictly ahead — push will send it
        else:
            merge = git.commit_tree(
                git.empty_tree(), b"merge", parents=[local_oid, remote_oid]
            )
            git.update_ref(f"refs/tasks/{ulid}", merge)  # join diverged heads

def push() -> None:
    """
    Push all local task refs to the remote.

    Sends refs/tasks/* to the identically-named refs on the remote.

    NOTE:  While ops are create-only every push is fast-forward — each ref
    is write-once, so a clone only ever adds refs the remote lacks and never 
    contends. The non-fast-forward retry loop is deferred to Milestone B.
    """
    git.push(REMOTE, PUSH_REFSPEC)