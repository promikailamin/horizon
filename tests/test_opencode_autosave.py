import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import opencode_autosave as autosave


def run(*args, cwd):
    return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True)


class AutosaveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.remote = root / "remote.git"
        self.repo = root / "repo"
        run("git", "init", "--bare", str(self.remote), cwd=root)
        run("git", "init", "-b", "main", str(self.repo), cwd=root)
        autosave.git("config", "user.name", "test", repo=self.repo)
        autosave.git("config", "user.email", "test@example.com", repo=self.repo)
        (self.repo / "file.txt").write_text("base")
        autosave.commit(self.repo, "initial")
        autosave.git("remote", "add", "origin", str(self.remote), repo=self.repo)
        autosave.git("push", "-u", "origin", "main", repo=self.repo)

    def tearDown(self):
        self.temporary.cleanup()

    def show(self, revision):
        return run("git", "--git-dir", str(self.remote), "show", revision,
                   cwd=self.repo).stdout

    def test_a_changed_workspace_is_committed_and_pushed(self):
        (self.repo / "file.txt").write_text("changed")
        self.assertEqual(
            autosave.once(self.repo, "main", "agent-recovery/issue-1"), "pushed")
        self.assertEqual(self.show("main:file.txt"), "changed")

    def test_a_clean_workspace_is_not_committed_again(self):
        self.assertEqual(
            autosave.once(self.repo, "main", "agent-recovery/issue-1"), "clean")

    def test_a_commit_that_loses_a_race_stays_on_the_recovery_branch(self):
        other = Path(self.temporary.name) / "other"
        run("git", "clone", "-b", "main", str(self.remote), str(other), cwd=self.repo)
        autosave.git("config", "user.name", "other", repo=other)
        autosave.git("config", "user.email", "other@example.com", repo=other)
        (other / "file.txt").write_text("theirs")
        autosave.commit(other, "theirs")
        autosave.git("push", "origin", "main", repo=other)

        (self.repo / "file.txt").write_text("ours")
        self.assertEqual(
            autosave.once(self.repo, "main", "agent-recovery/issue-1"), "recovery")
        self.assertEqual(self.show("agent-recovery/issue-1:file.txt"), "ours")

    def test_clean_but_unpushed_commits_are_still_pushed(self):
        (self.repo / "file.txt").write_text("local")
        autosave.commit(self.repo, "local")
        self.assertEqual(
            autosave.once(self.repo, "main", "agent-recovery/issue-1"), "up-to-date")
        self.assertEqual(self.show("main:file.txt"), "local")


if __name__ == "__main__":
    unittest.main()
