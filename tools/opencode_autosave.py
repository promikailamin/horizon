#!/usr/bin/env python3
"""Keep an OpenCode workspace recoverable while the job is still running.

GitHub Actions does not run a job's ``if: always()`` steps when the job itself is
cancelled, so a snapshot step at the end of an agent job cannot protect work a
cancelled run leaves behind. This tool commits the workspace periodically and
pushes those commits to the default branch. When that push loses a race, the
same commit is kept on ``agent-recovery/issue-<number>`` so the recovery job can
merge it instead of relying on an artifact that may never have been uploaded.

Only committed and pushed files survive a destroyed runner: the loop is the
recovery mechanism, the artifact is now a fallback.

Examples::

    python3 tools/opencode_autosave.py once --branch main \
        --recovery-branch agent-recovery/issue-3
    python3 tools/opencode_autosave.py loop --interval 120 --branch main
"""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
MESSAGE = "chore: autosave OpenCode workspace [skip ci]"
AUTHOR = ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com")


def git(*args: str, repo: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = ["git", *args]
    result = subprocess.run(command, cwd=repo, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        raise RuntimeError(f"{' '.join(command)} failed: {detail[-1] if detail else result.returncode}")
    return result


def commit(repo: Path = ROOT, message: str = MESSAGE) -> bool:
    """Stage and commit the worktree; False when there was nothing to save."""
    git("add", "-A", repo=repo)
    if git("diff", "--cached", "--quiet", repo=repo, check=False).returncode == 0:
        return False
    git("-c", f"user.name={AUTHOR[0]}", "-c", f"user.email={AUTHOR[1]}",
        "commit", "-m", message, repo=repo)
    return True


def has_commit(repo: Path, revision: str) -> bool:
    return git("rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}", repo=repo,
               check=False).returncode == 0


def push_main(repo: Path, remote: str, branch: str, attempts: int = 5) -> bool:
    """Push HEAD to the default branch, rebasing over other writers."""
    for attempt in range(1, attempts + 1):
        git("fetch", "--quiet", remote, branch, repo=repo, check=False)
        remote_ref = f"refs/remotes/{remote}/{branch}"
        if has_commit(repo, remote_ref) and \
                git("merge-base", "--is-ancestor", remote_ref, "HEAD", repo=repo,
                    check=False).returncode != 0:
            rebased = git("rebase", remote_ref, repo=repo, check=False)
            if rebased.returncode != 0:
                git("rebase", "--abort", repo=repo, check=False)
                return False
        pushed = git("push", remote, f"HEAD:refs/heads/{branch}", repo=repo, check=False)
        if pushed.returncode == 0:
            return True
        time.sleep(min(30, attempt * 3))
    return False


def push_recovery(repo: Path, remote: str, recovery_branch: str) -> bool:
    """Keep a commit that could not reach the default branch."""
    pushed = git("push", "--force", remote, f"HEAD:refs/heads/{recovery_branch}",
                 repo=repo, check=False)
    return pushed.returncode == 0


def ahead_of_remote(repo: Path, remote: str, branch: str) -> bool:
    git("fetch", "--quiet", remote, branch, repo=repo, check=False)
    remote_ref = f"refs/remotes/{remote}/{branch}"
    if not has_commit(repo, remote_ref):
        return True
    return git("rev-parse", remote_ref, repo=repo).stdout.strip() != \
        git("rev-parse", "HEAD", repo=repo).stdout.strip()


def once(repo: Path = ROOT, branch: str = "main", recovery_branch: str | None = None,
         remote: str = "origin") -> str:
    """Save one snapshot. Returns ``clean``, ``pushed`` or ``recovery``."""
    saved = commit(repo)
    if not saved and not ahead_of_remote(repo, remote, branch):
        return "clean"
    if push_main(repo, remote, branch):
        if recovery_branch:
            git("push", remote, "--delete", recovery_branch, repo=repo, check=False)
        return "pushed" if saved else "up-to-date"
    if recovery_branch and push_recovery(repo, remote, recovery_branch):
        return "recovery"
    return "failed"


def loop(repo: Path, interval: int, branch: str, recovery_branch: str | None,
         remote: str) -> None:
    stop = threading.Event()

    def request_stop(_signum, _frame):
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    while not stop.is_set():
        try:
            result = once(repo, branch, recovery_branch, remote)
            print(f"autosave: {result}", flush=True)
        except Exception as error:  # keep the loop alive; the next pass retries
            print(f"autosave: {error}", flush=True)
        stop.wait(interval)
    try:
        print(f"autosave: final {once(repo, branch, recovery_branch, remote)}", flush=True)
    except Exception as error:
        print(f"autosave: final {error}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["once", "loop"])
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--recovery-branch")
    parser.add_argument("--interval", type=int, default=120,
                        help="Seconds between snapshots in loop mode")
    args = parser.parse_args()
    if args.mode == "once":
        print(f"autosave: {once(args.repo, args.branch, args.recovery_branch, args.remote)}")
        return 0
    loop(args.repo, args.interval, args.branch, args.recovery_branch, args.remote)
    return 0


if __name__ == "__main__":
    sys.exit(main())
