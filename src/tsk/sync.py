from . import git

REMOTE = "origin"
FETCH_REFSPEC = "+refs/tasks/*:refs/remotes/origin/tasks/*"
PUSH_REFSPEC = "refs/tasks/*:refs/tasks/*"

def pull() -> None:
    """
    Fetch task refs from the remote and fast-forward local refs to match.

    Fetches refs/tasks/* into the tracking namespace, then for every task on
    the remote: adopts it if this clone lacks it, or fast-forwards the local
    ref when the remote is strictly ahead.

    NOTE: Local refs that are ahead of the remote are left for push to send;
    refs that have genuinely diverged are left untouched — merge handling is
    deferred to Milestone B.
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
        elif local_oid != remote_oid and git.is_ancestor(local_oid, remote_oid):
            git.update_ref(f"refs/tasks/{ulid}", remote_oid)  # fast-forward

def push() -> None:
    """
    Push all local task refs to the remote.

    Sends refs/tasks/* to the identically-named refs on the remote.

    NOTE:  While ops are create-only every push is fast-forward — each ref
    is write-once, so a clone only ever adds refs the remote lacks and never 
    contends. The non-fast-forward retry loop is deferred to Milestone B.
    """
    git.push(REMOTE, PUSH_REFSPEC)