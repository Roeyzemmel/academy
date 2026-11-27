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


class LeaseTests(Base):
    """#96: run leases on the homes, so two runs with disjoint instance sets share a checkout."""

    def test_a_lease_is_taken_refused_while_live_and_taken_over_when_stale(self):
        taken, refused = ac.lease_take(self.root, "run-a", {"sub": ["author@t"]}, pid=os.getpid())
        self.assertEqual((taken, refused), (["sub"], {}))
        lease = ac.read_lease(self.root, "sub")
        self.assertEqual((lease["run"], lease["instances"], lease["pid"]), ("run-a", ["author@t"], os.getpid()))
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".academy", "leases", "sub.json")))
        taken, refused = ac.lease_take(self.root, "run-b", ["sub", "other"])
        self.assertEqual(taken, ["other"])
        self.assertEqual(refused["sub"]["run"], "run-a")
        self.assertEqual(ac.lease_holder(self.root, "sub", "run-b")["run"], "run-a")
        self.assertIsNone(ac.lease_holder(self.root, "sub", "run-a"))      # its own
        # with its pid alive here, a long ticket between two heartbeats keeps it, up to the hours cap
        later = time.time() + (ac.LEASE_TIMEOUT_MINUTES + 1) * 60
        self.assertEqual(ac.lease_take(self.root, "run-b", ["sub"], now=later)[0], [])
        self.assertFalse(ac.lease_live(ac.read_lease(self.root, "sub"),
                                       now=time.time() + (ac.CLAIM_MAX_HOURS + 1) * 3600))
        # with no pid, stale by its heartbeat: taken over
        ac.lease_release(self.root, "run-a")
        ac.lease_take(self.root, "run-a", ["sub"])
        self.assertEqual(ac.lease_take(self.root, "run-b", ["sub"], now=later), (["sub"], {}))
        self.assertEqual(ac.read_lease(self.root, "sub")["run"], "run-b")

    def test_a_lease_whose_pid_is_gone_is_stale(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        ac.lease_take(self.root, "run-a", ["sub"], pid=p.pid)
        self.assertFalse(ac.lease_live(ac.read_lease(self.root, "sub")))
        self.assertEqual(ac.lease_take(self.root, "run-b", ["sub"]), (["sub"], {}))

    def test_the_snapshot_heartbeats_and_release_removes_only_its_own(self):
        start = time.time() - 20 * 60
        ac.lease_take(self.root, "run-a", ["sub"], now=start)
        ac.lease_take(self.root, "run-b", ["other"], now=start)
        ac.manifest_snapshot(self.root, "T-0001", run="run-a")
        self.assertGreater(ac.read_lease(self.root, "sub")["heartbeat"], start + 60)
        self.assertEqual(ac.read_lease(self.root, "sub")["started"], start)
        self.assertEqual(ac.read_lease(self.root, "other")["heartbeat"], start)
        self.assertEqual(ac.lease_release(self.root, "run-a"), ["sub"])
        self.assertEqual([x["target"] for x in ac.leases(self.root)], ["other"])

    def test_the_stop_check_leaves_a_leased_home_and_shipped_board_files_alone(self):
        ac.lease_take(self.root, "run-a", ["sub"])
        self.put(self.sub, "theirs.md")
        self.put(self.other, "loose.md")
        self.put(self.root, "board/packets/P-1.md")
        ac.record_shipped(self.root, "board", "board", ["packets/P-1.md"])
        self.assertEqual(ac.unclaimed_dirty(self.root), {"other": ["loose.md"]})
        self.put(self.root, "board/packets/P-1.md", "changed since its commit\n")
        self.assertEqual(ac.unclaimed_dirty(self.root), {"board": ["packets/P-1.md"], "other": ["loose.md"]})
        ac.lease_release(self.root, "run-a")
        self.assertIn("sub", ac.unclaimed_dirty(self.root))


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

    def test_lease_take_makes_a_unique_run_and_skips_a_leased_instance(self):
        ws = os.path.join(self.root, "workspace.json")
        with open(ws, "w", encoding="utf-8") as f:
            json.dump({"board": "board", "instances": {
                "author@t": {"role": "author", "home": os.path.join(self.root, "sub"), "domains": ["d"]},
                "expert@t": {"role": "expert", "home": os.path.join(self.root, "other"), "domains": ["d"]},
                # an attached checkout outside the workspace: leased by its directory's name
                "researcher@t": {"role": "researcher", "home": os.path.join(self.tmp, "lab"),
                                 "domains": ["d"]}}}, f)
        code, out, err = self.cli("lease", "take", "--prefix", "inbox-author@t", "--instances",
                                  "author@t", "--pid", str(os.getpid()))
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertRegex(lines[0], r"^run inbox-author@t-\d{8}T\d{6}-[0-9a-f]{4}$")
        self.assertEqual(lines[1], "leased author@t: sub")
        first = lines[0].split()[1]
        code, out, err = self.cli("lease", "take", "--prefix", "inbox-all", "--instances",
                                  "author@t,expert@t", "--instances", "researcher@t")
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        second = lines[0].split()[1]
        self.assertNotEqual(first, second)
        self.assertRegex(lines[1], r"^skipped author@t: sub is leased by run %s \(pid " % first)
        self.assertEqual(lines[2:], ["leased expert@t: other", "leased researcher@t: lab"])
        code, out, err = self.cli("lease", "list")
        self.assertEqual(code, 0, err)
        self.assertIn("sub: run %s" % first, out)
        code, out, err = self.cli("lease", "heartbeat", "--run", second)
        self.assertEqual(out.strip(), "heartbeat of run %s: lab other" % second)
        code, out, err = self.cli("lease", "release", "--run", second)
        self.assertEqual(out.strip(), "released for run %s: lab other" % second)
        code, out, err = self.cli("lease", "take", "--run", second, "--targets", "sub")
        self.assertIn("skipped sub: leased by run %s" % first, out)
        self.assertEqual(self.cli("lease", "release")[0], 2)            # needs --run


if __name__ == "__main__":
    unittest.main()
