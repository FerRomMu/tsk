import argparse
import subprocess

from . import git
from . import op
from . import fold
from . import sync

def cmd_sync(_):
    sync.run()

def cmd_new(args):
    task_id = op.write_create(args.title)
    print(task_id)

def cmd_ls(_):
    for task in fold.fold_all():
        if not task.deleted:
            print(task)

def cmd_mv(args):
    task_id = resolve_id(args.id)
    op.write_set_status(task_id, args.status)

def cmd_rm(args):
    task_id = resolve_id(args.id)
    op.write_set_deleted(task_id, True)

def cmd_edit(args):
    if args.title is None and args.body is None:
        raise SystemExit("tsk: edit needs at least one of --title or --body")
    task_id = resolve_id(args.id)
    if args.title is not None:
        op.write_set_title(task_id, args.title)
    if args.body is not None:
        op.write_set_body(task_id, args.body)

def cmd_show(args):
    task_id = resolve_id(args.id)
    task = fold.fold_ref(f"refs/tasks/{task_id}")
    print(f"task {task.id}")
    print(f"Status: {task.status}")
    print(f"Title:  {task.title}")
    if task.body:
        print()
        for line in task.body.splitlines():
            print(f"    {line}")

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

    synch = sub.add_parser("sync", help="Synchronize local tasks with remote")
    synch.set_defaults(func=cmd_sync)

    new = sub.add_parser("new", help="create a task")
    new.add_argument("title", help="the task title")
    new.set_defaults(func=cmd_new)

    ls = sub.add_parser("ls", help="list all tasks")
    ls.set_defaults(func=cmd_ls)

    mv = sub.add_parser("mv", help="change a task's status")
    mv.add_argument("id", help="the task id, or a unique prefix of it")
    mv.add_argument("status", help="the new status")
    mv.set_defaults(func=cmd_mv)

    rm = sub.add_parser("rm", help="deletes a task from the backlog")
    rm.add_argument("id", help="the task id, or a unique prefix of it")
    rm.set_defaults(func=cmd_rm)

    show = sub.add_parser("show", help="show one task in full")
    show.add_argument("id", help="the task id, or a unique prefix of it")
    show.set_defaults(func=cmd_show)

    edit = sub.add_parser("edit", help="change a task's title and/or body")
    edit.add_argument("id", help="the task id, or a unique prefix of it")
    edit.add_argument("--title", help="the new title")
    edit.add_argument("--body", help="the new body")
    edit.set_defaults(func=cmd_edit)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except subprocess.CalledProcessError as e:
        # git.run captures stderr, so git's own message would otherwise be
        # swallowed into a traceback with an empty-looking error.
        lines = [f"tsk: {' '.join(e.cmd)} failed"]
        detail = (e.stderr or b"").decode(errors="replace").strip()
        if detail:
            lines.append(detail)
        raise SystemExit("\n".join(lines))