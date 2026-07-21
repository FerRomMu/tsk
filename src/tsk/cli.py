import argparse

from . import op
from . import fold

def cmd_new(args):
    task_id = op.write_create(args.title)
    print(task_id)

def cmd_ls(_):
    for task in fold.fold_all():
        print(task)

def main(argv=None):
    parser = argparse.ArgumentParser(prog="tsk")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="create a task")
    new.add_argument("title", help="the task title")
    new.set_defaults(func=cmd_new)

    ls = sub.add_parser("ls", help="list all tasks")
    ls.set_defaults(func=cmd_ls)

    args = parser.parse_args(argv)
    args.func(args)