"""The checkpoint manifest (academy_common._manifest, #101 part 1): the snapshot diff that
attributes changed paths to a ticket, the run claims and their staleness, the stop check's
unclaimed set, and the manifest.py CLI. Temp repos only."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import academy_common as ac  # noqa: E402
from ship_fixture import add_submodule, make_workspace, run  # noqa: E402

MANIFEST_PY = os.path.join(PLUGIN, "scripts", "manifest.py")
STOP_PY = os.path.join(PLUGIN, "scripts", "stop_check.py")


class Base(unittest.TestCase):
    """A superproject with submodules 'sub' and 'other' and a plain board/ directory."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="manifest-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root, self.sub, _ = make_workspace(self.tmp)
        self.other, _ = add_submodule(self.tmp, self.root, "other")
        self.put(self.root, "board/README.md", "board\n")
        self.put(self.root, ".gitignore", "workspace.json\n")
        run(self.root, "add", ".gitignore", ".gitmodules", "board", "sub", "other")
        run(self.root, "commit", "-q", "-m", "init")
        with open(os.path.join(self.root, "workspace.json"), "w", encoding="utf-8") as f:
            json.dump({"instances": {}, "board": "board"}, f)

    def put(self, repo, rel, text="x\n"):
        path = os.path.join(repo, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path


class SnapshotDiffTests(Base):
    def test_targets_are_the_submodules_and_the_board(self):
        self.assertEqual([(t, p) for t, _, p in ac.manifest_targets(self.root)],
                         [("sub", None), ("other", None), ("board", "board")])

    def test_new_modified_untracked_and_deleted_paths_are_claimed(self):
        self.put(self.sub, "pre.txt", "the human's\n")               # dirty before
        claim = ac.manifest_snapshot(self.root, "T-0001")
        self.put(self.sub, "a.txt", "changed\n")                     # tracked, modified
        self.put(self.sub, "reviews/p/A.md", "verdict\n")            # untracked, nested dir
        os.remove(os.path.join(self.other, "a.txt"))                 # tracked, deleted
        self.put(self.root, "board/packets/P-1.md", "packet\n")      # the board
        self.put(self.root, "docs/x.md", "outside the board\n")      # superproject, not board
        self.assertEqual(ac.manifest_changed(self.root, claim),
                         {"sub": ["a.txt", "reviews/p/A.md"], "other": ["a.txt"],
                          "board": ["packets/P-1.md"]})

    def test_pre_dirty_unchanged_is_not_claimed_but_changed_is(self):
        self.put(self.sub, "pre.txt", "the human's\n")
        self.put(self.other, "a.txt", "a human edit\n")
        claim = ac.manifest_snapshot(self.root, "T-0001")
        self.assertEqual(claim["repos"]["sub"].keys(), {"pre.txt"})
        self.assertEqual(ac.manifest_changed(self.root, claim), {})
        self.put(self.other, "a.txt", "a human edit\nand the ticket's line\n")
        self.assertEqual(ac.manifest_changed(self.root, claim), {"other": ["a.txt"]})

    def test_nested_repositories_and_pointers_are_left_out(self):
        claim = ac.manifest_snapshot(self.root, "T-0001")
        nested = os.path.join(self.sub, "vendor")
        os.makedirs(nested)
        run(nested, "init", "-q")
        self.put(nested, "f.txt")
        self.assertEqual(ac.manifest_changed(self.root, claim), {})

    def test_the_claim_file_lives_under_a_self_ignoring_directory(self):
        ac.manifest_snapshot(self.root, "T-0001", run="inbox-all")
        f, c = ac.find_claim(self.root, "T-0001")
        self.assertEqual(os.path.basename(f), "inbox-all-T-0001.json")
        self.assertEqual(c["ticket"], "T-0001")
        self.assertEqual(run(self.root, "status", "--porcelain", "--untracked-files=all"), "")

    def test_claims_are_per_run_and_ticket_so_concurrent_runs_never_overwrite(self):
        ac.manifest_snapshot(self.root, "T-0001", run="inbox-all")
        ac.manifest_snapshot(self.root, "T-0002", run="inbox-all")      # another run, same id
        self.assertEqual(os.path.basename(ac.find_claim(self.root, "T-0001")[0]),
                         "inbox-all-T-0001.json")
        self.assertEqual(ac.find_claim(self.root, "T-0002")[1]["run"], "inbox-all")

    def test_stale_claims_are_removed_at_the_next_snapshot(self):
        ac.manifest_snapshot(self.root, "T-0001", run="r1", now=time.time() - 7 * 3600)
        ac.manifest_snapshot(self.root, "T-0002", run="r2")
        self.assertEqual(ac.find_claim(self.root, "T-0001"), (None, None))
        self.assertEqual(ac.prune_claims(self.root), 0)

    def test_a_home_unreadable_at_the_snapshot_is_recorded_and_never_claimed(self):
        self.put(self.other, "pre.txt", "dirty before the ticket\n")
        git_dir = os.path.join(self.other, ".git")
        os.rename(git_dir, git_dir + ".away")
        with open(git_dir, "w") as f:
            f.write("gitdir: /nowhere\n")
        claim = ac.manifest_snapshot(self.root, "T-0001")
        os.remove(git_dir)
        os.rename(git_dir + ".away", git_dir)
        self.assertEqual(claim["failed"], ["other"])
        self.put(self.sub, "new.md")
        self.assertEqual(ac.manifest_changed(self.root, claim), {"sub": ["new.md"]})

    def test_a_large_file_is_compared_by_size_and_mtime_not_hashed(self):
        path = self.put(self.sub, "big.bin", "y" * 64)
        with mock.patch.object(ac, "MANIFEST_HASH_CAP", 16):
            h = ac.manifest_hash(path)
            self.assertTrue(h.startswith("size:64:"), h)
            claim = ac.manifest_snapshot(self.root, "T-0001")
            self.assertEqual(ac.manifest_changed(self.root, claim), {})
            self.put(self.sub, "big.bin", "z" * 65)
            self.assertEqual(ac.manifest_changed(self.root, claim), {"sub": ["big.bin"]})

    def test_bad_names_are_refused(self):
        with self.assertRaises(ac.ManifestError):
            ac.manifest_snapshot(self.root, "../T-1")
        with self.assertRaises(ac.ManifestError):
            ac.manifest_snapshot(self.root, "T-1", run="a/b")

    def test_pending_manifest_merges_and_empties(self):
        ac.save_pending(self.root, "T-0001", {"sub": ["a.txt"]})
        ac.save_pending(self.root, "T-0001", ac.merge_manifest(
            ac.load_pending(self.root, "T-0001")["repos"], {"sub": ["b.txt"], "board": ["p.md"]}))
        self.assertEqual(ac.load_pending(self.root, "T-0001")["repos"],
                         {"sub": ["a.txt", "b.txt"], "board": ["p.md"]})
        ac.save_pending(self.root, "T-0001", {})
        self.assertIsNone(ac.load_pending(self.root, "T-0001"))


class StopCheckTests(Base):
    def test_live_claim_hides_its_changes_and_nothing_else(self):
        self.put(self.sub, "pre.txt", "the human's\n")
        ac.manifest_snapshot(self.root, "T-0001", run="r1")
        self.put(self.sub, "a.txt", "the ticket's\n")
        self.put(self.root, "board/packets/P-1.md")
        self.assertEqual(ac.unclaimed_dirty(self.root), {"sub": ["pre.txt"]})

    def test_stale_claim_by_age_is_ignored(self):
        ac.manifest_snapshot(self.root, "T-0001", run="r1", now=time.time() - 7 * 3600)
        self.put(self.sub, "a.txt", "the ticket's\n")
        self.assertEqual(ac.unclaimed_dirty(self.root), {"sub": ["a.txt"]})

    def test_stale_claim_by_dead_pid_is_ignored(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        ac.manifest_snapshot(self.root, "T-0001", run="r1", pid=p.pid)
        self.put(self.sub, "a.txt", "the ticket's\n")
        self.assertEqual(ac.unclaimed_dirty(self.root), {"sub": ["a.txt"]})
        ac.manifest_snapshot(self.root, "T-0001", run="r1", pid=os.getpid())
        self.put(self.sub, "a.txt", "the ticket's, again\n")
        self.assertEqual(ac.unclaimed_dirty(self.root), {})

    def test_hook_blocks_on_unclaimed_and_is_silent_on_claimed(self):
        ws = os.path.join(self.root, "workspace.json")
        with open(ws, "w", encoding="utf-8") as f:
            json.dump({"instances": {}, "board": "board", "stopCheck": True}, f)
        env = dict(os.environ, ACADEMY_WORKSPACE=ws)

        def hook(event):
            p = subprocess.run([sys.executable, STOP_PY], input=json.dumps(event), text=True,
                               capture_output=True, env=env, cwd=self.root, timeout=60)
            return p.returncode, p.stdout.strip()

        ac.manifest_snapshot(self.root, "T-0001", run="r1")
        self.put(self.sub, "a.txt", "the ticket's\n")
        self.assertEqual(hook({"cwd": self.root}), (0, ""))
        # dirty before the snapshot: not the run's (anything changed after it is hidden
        # while the claim is live, whoever made it)
        ac.release_claim(ac.find_claim(self.root, "T-0001")[0])
        self.put(self.other, "loose.txt")
        ac.manifest_snapshot(self.root, "T-0001", run="r1")
        self.put(self.sub, "a.txt", "the ticket's, again\n")
        code, out = hook({"cwd": self.root})
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual(doc["decision"], "block")
        self.assertIn("other/loose.txt", doc["reason"])
        self.assertNotIn("sub/a.txt", doc["reason"])
        self.assertEqual(hook({"cwd": self.root, "stop_hook_active": True}), (0, ""))
        with open(ws, "w", encoding="utf-8") as f:                      # opt-in only
            json.dump({"instances": {}, "board": "board"}, f)
        self.assertEqual(hook({"cwd": self.root}), (0, ""))


class CliTests(Base):
    def cli(self, *argv):
        ws = os.path.join(self.root, "workspace.json")
        p = subprocess.run([sys.executable, MANIFEST_PY, "--workspace", ws, *argv],
                           capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout, p.stderr

    def test_snapshot_then_diff(self):
        code, out, err = self.cli("snapshot", "--ticket", "T-0007", "--run", "inbox-all")
        self.assertEqual(code, 0, err)
        self.assertIn("T-0007", out)
        self.put(self.sub, "new.md")
        code, out, err = self.cli("diff", "--ticket", "T-0007", "--json")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["repos"], {"sub": ["new.md"]})
        code, out, err = self.cli("unclaimed")
        self.assertEqual((code, out.strip()), (0, "(nothing unclaimed)"))
        code, out, err = self.cli("diff", "--ticket", "T-9999")
        self.assertEqual(code, 1)


class PidProbeTests(unittest.TestCase):
    """os.kill(pid, 0) is no probe on Windows (signal 0 is CTRL_C_EVENT): it is never called
    there, and the claim's age decides; elsewhere it still tells a dead pid."""
    def test_windows_never_signals(self):
        from academy_common import _manifest as mf
        with mock.patch.object(mf.os, "name", "nt"), \
                mock.patch.object(mf.os, "kill", side_effect=AssertionError("os.kill called on Windows")):
            self.assertTrue(mf._mf_pid_alive(12345))

    def test_posix_tells_a_dead_pid(self):
        from academy_common import _manifest as mf
        if os.name == "nt":
            self.skipTest("POSIX only")
        with mock.patch.object(mf.os, "kill", side_effect=ProcessLookupError):
            self.assertFalse(mf._mf_pid_alive(12345))
        self.assertTrue(mf._mf_pid_alive(os.getpid()))


if __name__ == "__main__":
    unittest.main()
