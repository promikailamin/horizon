#!/usr/bin/env python3
"""Remove stale branches from this fork.

By default only branches already merged into the default branch are listed;
``--delete`` removes them from the remote. Commits stay reachable from the
default branch, so deleting a merged branch loses no work. ``--all`` also
offers unmerged branches (not done automatically: their commits may be the only
copy in this fork).

Examples::

    python3 tools/cleanup_branches.py
    python3 tools/cleanup_branches.py --delete
    python3 tools/cleanup_branches.py --all --keep 'release/*'
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def git(*args: str, check: bool = True) -> str:
    return subprocess.run(["git", *args], check=check, text=True,
                          capture_output=True).stdout


def branches(remote: str, default: str, merged_only: bool) -> list[str]:
    args = ["branch", "-r"]
    if merged_only:
        args.append("--merged")
        args.append(f"{remote}/{default}")
    output = git(*args)
    prefix = f"{remote}/"
    names = []
    for line in output.splitlines():
        name = line.strip().removeprefix("* ").strip()
        if not name.startswith(prefix):
            continue
        name = name[len(prefix):]
        if name in (default, "HEAD") or " -> " in name:
            continue
        names.append(name)
    return sorted(set(names))


def delete(remote: str, names: list[str], batch: int = 20) -> None:
    for start in range(0, len(names), batch):
        group = names[start:start + batch]
        # A branch deleted elsewhere (a race with another cleanup) must not stop
        # the rest: the next fetch simply won't show it.
        subprocess.run(["git", "push", remote, "--delete", *group], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--default", default="main")
    parser.add_argument("--keep", action="append", default=[],
                        help="glob of branch names to keep (repeatable)")
    parser.add_argument("--all", action="store_true",
                        help="Include branches not merged into the default branch")
    parser.add_argument("--delete", action="store_true",
                        help="Delete the listed branches from the remote")
    args = parser.parse_args()

    git("fetch", "--quiet", args.remote)
    names = branches(args.remote, args.default, merged_only=not args.all)
    if args.keep:
        import fnmatch
        names = [n for n in names if not any(fnmatch.fnmatch(n, p) for p in args.keep)]
    if not names:
        print("Nothing to clean.")
        return
    for name in names:
        print(name)
    print(f"{len(names)} branch(es)")
    if not args.delete:
        print("Dry run: pass --delete to remove them from the remote.")
        return
    delete(args.remote, names)
    print(f"Deleted {len(names)} branch(es) from {args.remote}.")


if __name__ == "__main__":
    sys.exit(main())
