from . import git

REMOTE = "origin"
FETCH_REFSPEC = "+refs/tasks/*:refs/remotes/origin/tasks/*"
PUSH_REFSPEC = "refs/tasks/*:refs/tasks/*"

def pull() -> None:
    """
    Fetch task refs from the remote and adopt any this clone is missing.

    Fetches refs/tasks/* into the tracking namespace, then for every task
    present on the remote but absent locally, points a local ref at it.
    
    NOTE: Refs already held locally are left untouched — while ops are 
    create-only they cannot have diverged. Divergence handling is deferred
    to Milestone B.
    """
    git.fetch(REMOTE, FETCH_REFSPEC)

    local = {ref.rsplit("/", 1)[1] for ref, _ in git.for_each_ref("refs/tasks/*")} # SET ULID Refs
    for ref, oid in git.for_each_ref("refs/remotes/origin/tasks/*"):
        ulid = ref.rsplit("/", 1)[1]
        if ulid not in local:
            git.update_ref(f"refs/tasks/{ulid}", oid)

def push() -> None:
    """
    Push all local task refs to the remote.

    NOTE: Sends refs/tasks/* to the identically-named refs on the remote. While
    ops are create-only every push is fast-forward — each ref is write-once,
    so a clone only ever adds refs the remote lacks and never contends. The
    non-fast-forward retry loop is deferred to Milestone B.
    """
    git.push(REMOTE, PUSH_REFSPEC)