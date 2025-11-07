#!/usr/bin/env python3

from concurrent.futures import ProcessPoolExecutor, as_completed
import sys
import io
import argparse
from pathlib import Path

parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from base import git,submodule_top_down,cprint,_git_fetch,print_changes_bothsides,remote_repo_name,_main_branch

ORIGINMASTER = "o/m"

def sublog(args, git=git):
    # submit fetch
    futures_fetch = set()
    if args.fetch:
        with ProcessPoolExecutor() as ex:
            def add_future_fetch(git, lvl):
                nonlocal futures_fetch
                futures_fetch.add(ex.submit(_git_fetch,git.path))
            submodule_top_down(add_future_fetch, git=git)

    # submit main branch
    futures_main_branch = set()
    if args.fr == ORIGINMASTER:
        with ProcessPoolExecutor() as ex:
            def add_future_main_branch(git, lvl):
                nonlocal futures_main_branch
                fut = ex.submit(_main_branch,git.path)
                futures_main_branch.add(fut)
            submodule_top_down(add_future_main_branch, git=git)

    # wait for completion of all submissions
    # 'wait' is not an alternative, because it doesn't throw errors 
    for fut in as_completed(futures_fetch):
        _ = fut.result()
    
    main_branches = dict(fut.result() for fut in as_completed(futures_main_branch))

    # recursive log
    def _sublog(git, lvl):
        buffer = io.StringIO()
        sys.stdout = buffer
        fr = "origin/"+ main_branches[git.path] if args.fr == ORIGINMASTER else args.fr
        to = args.to
        diff_size = print_changes_bothsides(fr, to, git=git, color_subrefs=True)
        sys.stdout = sys.__stdout__
        if diff_size > 0:
            match args.repo_label:
                case "remote":
                    repo_label = remote_repo_name(git=git)
                case "relpath":
                    repo_label = Path(git.path).resolve().relative_to(Path("..").resolve())
                case "abspath":
                    repo_label = Path(git.path).resolve()
                case "dirname":
                    repo_label = Path(git.path).resolve().name
                case _:
                    raise Exception("invalid `repo_label`")
            repo_label = str(repo_label)
            cprint(repo_label.center(65,"-"),fg_color="yellow")
            print(buffer.getvalue(), end="")
        elif args.stop_unchanged:
            return False
    submodule_top_down(_sublog, git=git)


def parse_arguments():
    parser = argparse.ArgumentParser()

    fetch_group = parser.add_mutually_exclusive_group()
    fetch_group.add_argument(
        "--fetch",
        dest="fetch",
        action="store_true",
        help="Enable fetch mode"
    )
    fetch_group.add_argument(
        "--no-fetch",
        dest="fetch",
        action="store_false",
        help="Disable fetch mode (default)"
    )
    parser.set_defaults(fetch=False)

    stop_unchanged_group = parser.add_mutually_exclusive_group()
    stop_unchanged_group.add_argument(
        "--stop-unchanged",
        dest="stop_unchanged",
        action="store_true",
        help="Don't go deeper in recursion if there is no change in submodule (default)"
    )

    stop_unchanged_group.add_argument(
        "--no-stop-unchanged",
        dest="stop_unchanged",
        action="store_false",
        help="Goes into every submodule"
    )

    parser.set_defaults(stop_unchanged=True)

    parser.add_argument(
        "--repo-label",
        choices=["remote", "relpath", "abspath", "dirname"],
        default="dirname",
        help="Adjust how you see the repo label"
    )

    parser.add_argument("fr", nargs="?", default=ORIGINMASTER,help="Chose to comparison: theirs/from (optional)")
    parser.add_argument("to", nargs="?", default="HEAD", help="Chose to comparison: ours/to (optional)")

    return parser.parse_args()



if __name__ == "__main__":
    args = parse_arguments()
    sublog(args,git=git)
