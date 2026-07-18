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