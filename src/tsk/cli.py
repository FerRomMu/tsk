import argparse

from . import git
from . import op
from . import fold

def cmd_new(args):
    task_id = op.write_create(args.title)
    print(task_id)

def cmd_ls(_):
    for task in fold.fold_all():
        print(task)

def cmd_mv(args):
    task_id = resolve_id(args.id)
    op.write_set_status(task_id, args.status)

def resolve_id(prefix: str) -> str:
    """
    Resolve a task id or unique prefix to its full ULID.

    Args:
        prefix: a full ULID or a unique prefix of one.

    Returns:
        The matching task's full ULID.

    Raises:
        SystemExit: if no task or more than one task matches.
    """
    matches = [
        ref.removeprefix("refs/tasks/")
        for ref, _ in git.for_each_ref("refs/tasks/*")
        if ref.removeprefix("refs/tasks/").startswith(prefix)
    ]
    if not matches:
        raise SystemExit(f"tsk: no task matches '{prefix}'")
    if len(matches) > 1:
        raise SystemExit(f"tsk: '{prefix}' is ambiguous, matches {', '.join(matches)}")
    return matches[0]

def main(argv=None):
    parser = argparse.ArgumentParser(prog="tsk")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="create a task")
    new.add_argument("title", help="the task title")
    new.set_defaults(func=cmd_new)

    ls = sub.add_parser("ls", help="list all tasks")
    ls.set_defaults(func=cmd_ls)

    mv = sub.add_parser("mv", help="change a task's status")
    mv.add_argument("id", help="the task id, or a unique prefix of it")
    mv.add_argument("status", help="the new status")
    mv.set_defaults(func=cmd_mv)

    args = parser.parse_args(argv)
    args.func(args)