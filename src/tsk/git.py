import subprocess

def run(args: list[str], stdin: bytes | None = None) -> bytes:
    """
    Run a git command and return its stdout.

    Args:
        args: The arguments to pass to the git command.
        stdin: The standard input to pass to the git command.
    
    Returns:
        The standard output of the git command.

    Raises:
        subprocess.CalledProcessError: If the git command fails.
    """
    return subprocess.run(
            ["git", *args],
            input=stdin,
            capture_output=True,
            check=True,
        ).stdout

def hash_object(content: bytes) -> str:
    """
    Writes 'Data' as a blob object in the object database.

    Args:
        content: The content to write.

    Returns:
        Its OID (Object ID).
    """
    return run(["hash-object", "-w", "--stdin"], stdin=content).decode().strip()

def mktree(entries: list[tuple[str, str, str, str]]) -> str:
    """
    Create a tree object from a list of entries.

    Args:
        entries: rows of (mode, type, oid, name).

    Returns:
        The new tree's OID.
    """
    lines = "".join(
        f"{mode} {otype} {oid}\t{name}\n"
        for mode, otype, oid, name in entries
    )
    return run(["mktree"], stdin=lines.encode()).decode().strip()

def commit_tree(tree: str, message: bytes, parents: list[str] = ()) -> str:
    """
    Create a commit object pointing at a tree.

    Args:
        tree: the tree OID this commit snapshots.
        message: the commit message, as bytes.
        parents: parent commit OIDs — empty for a root commit,
            one for a normal child, two for a merge.

    Returns:
        The new commit's OID.
    """
    args = ["commit-tree", tree]
    for parent in parents:
        args += ["-p", parent]
    return run(args, message + b"\n").decode().strip()

def update_ref(ref: str, new_oid: str, old_oid: str | None = None) -> None:
    """
    Point a ref at a commit.

    Args:
        ref: the full ref name, e.g. "refs/tasks/<ULID>".
        new_oid: the commit OID the ref should point to.
        old_oid: if given, the update only succeeds when the ref
            currently points here (compare-and-swap). Pass the empty
            string to require that the ref does not yet exist.
    """
    args = ["update-ref", ref, new_oid]
    if old_oid is not None:
        args.append(old_oid)
    run(args)

def for_each_ref(pattern: str) -> list[tuple[str, str]]:
    """
    List refs matching a pattern.

    Args:
        pattern: a ref glob, e.g. "refs/tasks/*".

    Returns:
        (refname, oid) for each matching ref.
    """
    out = run(["for-each-ref", "--format=%(refname) %(objectname)", pattern]).decode()
    result = []
    for line in out.splitlines():
        refname, oid = line.split()
        result.append((refname, oid))
    return result

def rev_list(ref: str) -> list[str]:
    """
    List the commit OIDs reachable from a ref.

    Args:
        ref: a ref name or commit-ish, e.g. "refs/tasks/<ULID>".

    Returns:
        Commit OIDs reachable from ref, newest first.
    """
    return run(["rev-list", ref]).decode().split()

def cat_file(oid: str) -> bytes:
    """
    Read an object's content.

    Args:
        oid: an object name — a blob OID, or a path form like
            "<commit>:op" to read the blob at that path in a commit.

    Returns:
        The object's raw content.
    """
    return run(["cat-file", "-p", oid])