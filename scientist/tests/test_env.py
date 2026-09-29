"""Tests for scripts/env.py: env profiles (wsl | local | ssh), the policy, and the job
queue that speaks the fsq runner protocol.

No network and no remote: ssh and scp are replaced by ``fixtures/fake_ssh.py``
(ACADEMY_SSH / ACADEMY_SCP), the VPN preflight by ACADEMY_FAKE_PREFLIGHT, and the
remote git repository by a local bare repo (the profile's test-only ``pushUrl``,
as in the legacy queue.ps1). The lab home is a temporary git repository.

Run: py -m unittest discover -s tests -t tests   (from the plugin folder)
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
SCRIPTS = os.path.join(PLUGIN, "scripts")
ENVPY = os.path.join(SCRIPTS, "env.py")
FAKE = os.path.join(HERE, "fixtures", "fake_ssh.py")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def runner_hash():
    with open(os.path.join(SCRIPTS, "fsq.sh"), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True)


class Lab(object):
    """A temp lab home (git repo, academy.json), a bare 'remote', a fake remote root."""

    def __init__(self, config_extra=None, with_config=True):
        self.root = tempfile.mkdtemp(prefix="envtest-")
        self.home = os.path.join(self.root, "lab")
        self.bare = os.path.join(self.root, "remote.git")
        self.remote_root = os.path.join(self.root, "remote-home")
        os.makedirs(self.remote_root)
        os.makedirs(self.home)
        git(self.root, "init", "-q", "--bare", self.bare)
        git(self.home, "init", "-q")
        git(self.home, "config", "user.email", "t@example.invalid")
        git(self.home, "config", "user.name", "T")
        git(self.home, "config", "core.autocrlf", "false")
        self.write("experiments/2026-09-01_e1.py", "print(1)\n")
        self.write("experiments/_template.py", "\n")
        self.write(".gitignore", "queue/pending/\nqueue/running/\nqueue/done/\nqueue/parked/\n")
        self.cfg = {
            "schema": 1, "role": "scientist", "instance": "scientist@main",
            "domains": ["translation-surfaces"], "ns": "lab",
            "paths": {"package": "fslab", "experiments": "experiments/*.py",
                      "results": "results", "queue": "queue", "records": "claims",
                      "views": ["claims/INDEX.md"]},
            "registry": {"profile": "lab", "root": "claims"},
            "scientist": {
                "envs": {
                    "laptop-wsl": {"kind": "wsl", "distro": "Ubuntu", "conda": "flatsurf"},
                    "local": {"kind": "local", "conda": "flatsurf"},
                    "lingo": {"kind": "ssh", "host": "lingo",
                              "prefix": "/data/u/miniforge3", "env": "flatsurf",
                              "repo": "~/SciLab", "maxJobs": 1,
                              "preflight": "vpn:globalprotect",
                              "pushUrl": self.bare}},
                "policy": {"probe": "laptop-wsl", "test": "laptop-wsl", "run": "lingo"},
                "queue": {"dir": "queue", "fsqHome": "~/fsq", "maxJobs": 1}},
        }
        if config_extra:
            config_extra(self.cfg)
        if with_config:
            self.write(".claude/academy.json", json.dumps(self.cfg, indent=2))
        git(self.home, "add", "-A")
        git(self.home, "commit", "-q", "-m", "init")
        self.state_path = os.path.join(self.root, "fake-state.json")
        self.log_path = os.path.join(self.root, "fake-log.jsonl")
        self.set_state({"reachable": True, "version": runner_hash(), "max": 1, "spool": {}})
        self.env = dict(os.environ, PYTHONIOENCODING="utf-8",
                        ACADEMY_SSH=json.dumps([sys.executable, FAKE]),
                        ACADEMY_SCP=json.dumps([sys.executable, FAKE, "--scp"]),
                        ACADEMY_FAKE_PREFLIGHT="0",
                        FAKE_SSH_STATE=self.state_path, FAKE_SSH_LOG=self.log_path,
                        FAKE_REMOTE_ROOT=self.remote_root)
        self.env.pop("ACADEMY_LAB_HOME", None)

    def write(self, rel, text):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return path

    def set_state(self, state):
        with open(self.state_path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)

    def state(self):
        with open(self.state_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def calls(self):
        if not os.path.isfile(self.log_path):
            return []
        with open(self.log_path, "r", encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def ssh_cmds(self):
        return [c["cmd"] for c in self.calls() if c["mode"] == "ssh"]

    def run(self, *args, cwd=None, env=None):
        proc = subprocess.run([sys.executable, ENVPY, "--home", self.home] + list(args),
                              capture_output=True, text=True, encoding="utf-8",
                              env=env or self.env, cwd=cwd or self.home)
        return proc.returncode, proc.stdout, proc.stderr

    def jobs(self, state):
        d = os.path.join(self.home, "queue", state)
        if not os.path.isdir(d):
            return []
        out = []
        for f in sorted(os.listdir(d)):
            with open(os.path.join(d, f), "r", encoding="utf-8-sig") as fh:
                out.append(json.load(fh))
        return out

    def put_job(self, state, job):
        d = os.path.join(self.home, "queue", state)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, job["id"] + ".json"), "w", encoding="utf-8") as fh:
            json.dump(job, fh, indent=4)

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class EnvCase(unittest.TestCase):
    def setUp(self):
        self.lab = Lab()
        self.addCleanup(self.lab.close)


# -- profiles -----------------------------------------------------------------

class TestProfiles(EnvCase):
    def test_runner_copy_is_the_legacy_runner(self):
        with open(os.path.join(SCRIPTS, "legacy", "fsq.sh"), "rb") as fh:
            legacy = fh.read()
        with open(os.path.join(SCRIPTS, "fsq.sh"), "rb") as fh:
            self.assertEqual(fh.read(), legacy, "fsq.sh must stay byte-identical to the "
                             "deployed runner until a redeploy is decided")

    def test_list(self):
        rc, out, err = self.lab.run("list")
        self.assertEqual(rc, 0, err)
        self.assertIn("laptop-wsl", out)
        self.assertIn("wsl", out)
        self.assertIn("lingo", out)
        self.assertIn("ssh", out)
        self.assertRegex(out, r"run\s*=\s*lingo")
        rc, out, err = self.lab.run("list", "--json")
        data = json.loads(out)
        self.assertEqual(data["policy"]["run"], "lingo")
        self.assertEqual(data["envs"]["lingo"]["kind"], "ssh")

    def test_resolve_by_name_or_policy_key(self):
        import env
        lab = env.load_lab(self.lab.home)
        self.assertEqual(env.resolve_profile(lab, "run")[0], "lingo")
        self.assertEqual(env.resolve_profile(lab, "test")[0], "laptop-wsl")
        self.assertEqual(env.resolve_profile(lab, "local")[0], "local")
        with self.assertRaises(env.EnvError):
            env.resolve_profile(lab, "nope")
        # the legacy run.ps1 targets
        self.assertEqual(env.resolve_profile(lab, "wsl")[0], "laptop-wsl")
        self.assertEqual(env.resolve_profile(lab, "wsl:Ubuntu")[0], "laptop-wsl")
        self.assertEqual(env.resolve_profile(lab, "ssh:lingo")[0], "lingo")
        name, prof = env.resolve_profile(lab, "wsl:Debian")      # ad hoc
        self.assertEqual((prof["kind"], prof["distro"]), ("wsl", "Debian"))
        with self.assertRaises(env.EnvError):
            env.resolve_profile(lab, "ssh:elsewhere")            # never an ad-hoc host

    def test_static_problems(self):
        import env
        self.assertEqual(env.static_problems("x", {"kind": "ssh", "host": "h"}), [])
        self.assertIn("needs host", env.static_problems("x", {"kind": "ssh"})[0])
        self.assertIn("needs distro", env.static_problems("x", {"kind": "wsl"})[0])
        self.assertIn("kind", env.static_problems("x", {"kind": "vm"})[0])
        self.assertIn("preflight", env.static_problems(
            "x", {"kind": "ssh", "host": "h", "preflight": "nonsense"})[0])
        self.assertIn("maxJobs", env.static_problems(
            "x", {"kind": "ssh", "host": "h", "maxJobs": 7})[0])

    def test_pre_switch_home_uses_queue_config(self):
        lab = Lab(with_config=False)
        self.addCleanup(lab.close)
        lab.write("queue/config.json", json.dumps(
            {"target": "ssh:lingo", "prefix": "/p", "remoteRepo": "~/SciLab",
             "fsqHome": "~/fsq", "maxJobs": 1}))
        import env
        l = env.load_lab(lab.home)
        name, prof = env.resolve_profile(l, "run")
        self.assertEqual(prof["kind"], "ssh")
        self.assertEqual(prof["host"], "lingo")
        self.assertEqual(prof["prefix"], "/p")


class TestCheck(EnvCase):
    def test_check_ssh_offline_runs_only_the_preflight(self):
        rc, out, err = self.lab.run("check", "lingo")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("preflight vpn:globalprotect: up", out)
        self.assertEqual(self.lab.calls(), [], "no ssh without --live")

    def test_check_preflight_down_means_queued(self):
        env_ = dict(self.lab.env, ACADEMY_FAKE_PREFLIGHT="1")
        rc, out, err = self.lab.run("check", "lingo", "--live", env=env_)
        self.assertEqual(rc, 1)
        self.assertIn("unreachable", out)
        self.assertIn("queued", out)
        self.assertEqual(self.lab.calls(), [])

    def test_check_live_asks_version_and_status_only(self):
        rc, out, err = self.lab.run("check", "lingo", "--live")
        self.assertEqual(rc, 0, out + err)
        cmds = self.lab.ssh_cmds()
        self.assertEqual(len(cmds), 2, cmds)
        self.assertTrue(cmds[0].endswith("~/fsq/bin/fsq version"), cmds)
        self.assertTrue(cmds[1].endswith("~/fsq/bin/fsq status"), cmds)
        self.assertIn("matches", out)
        self.assertIn("#max", out)

    def test_check_live_reports_a_different_runner(self):
        st = self.lab.state(); st["version"] = "0" * 64; self.lab.set_state(st)
        rc, out, err = self.lab.run("check", "lingo", "--live")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("differs", out)

    def test_check_live_unreachable_host(self):
        st = self.lab.state(); st["reachable"] = False; self.lab.set_state(st)
        rc, out, err = self.lab.run("check", "lingo", "--live")
        self.assertEqual(rc, 1)
        self.assertIn("unreachable", out)


class TestRun(EnvCase):
    def test_run_refuses_ssh(self):
        rc, out, err = self.lab.run("run", "lingo", "experiments/2026-09-01_e1.py")
        self.assertEqual(rc, 2)
        self.assertIn("queue", err)

    def test_run_wsl_command(self):
        rc, out, err = self.lab.run("run", "laptop-wsl", "--dry-run", "--sage",
                                    "experiments/2026-09-01_e1.py", "--bound", "4 0")
        self.assertEqual(rc, 0, err)
        argv = json.loads(out)
        self.assertEqual(argv[:4], ["wsl.exe", "-d", "Ubuntu", "--"])
        self.assertEqual(argv[4:6], ["bash", "-lc"])
        cmd = argv[6]
        self.assertIn("FLATSURF_ENV='flatsurf'", cmd)
        self.assertIn("SAGE=1", cmd)
        self.assertIn("LAB_ROOT=", cmd)
        self.assertIn("run.sh", cmd)
        self.assertIn("'experiments/2026-09-01_e1.py' '--bound' '4 0'", cmd)

    def test_run_policy_key_and_code(self):
        rc, out, err = self.lab.run("run", "test", "--dry-run", "-c", "print('hi')")
        self.assertEqual(rc, 0, err)
        argv = json.loads(out)
        self.assertIn("-c 'print('\\''hi'\\'')'", argv[-1])

    def test_run_legacy_flags(self):
        """lab.py cmd run passes run.ps1-style arguments: -Code, -Target, -Sage, a script."""
        rc, out, err = self.lab.run("run", "-Code", "print(1)", "-Sage", "--dry-run")
        self.assertEqual(rc, 0, err)
        argv = json.loads(out)
        self.assertEqual(argv[:3], ["wsl.exe", "-d", "Ubuntu"])
        self.assertIn("SAGE=1", argv[-1])
        self.assertIn("-c 'print(1)'", argv[-1])
        rc, out, err = self.lab.run("run", "-u", "--dry-run", "experiments/2026-09-01_e1.py",
                                    "--bound", "3")
        self.assertEqual(rc, 0, err)
        self.assertIn("'experiments/2026-09-01_e1.py' '--bound' '3'", json.loads(out)[-1])
        rc, out, err = self.lab.run("run", "-Target", "ssh:lingo", "-Code", "print(1)")
        self.assertEqual(rc, 2)
        self.assertIn("queue", err)

    def test_run_local_command(self):
        rc, out, err = self.lab.run("run", "local", "--dry-run", "experiments/2026-09-01_e1.py")
        self.assertEqual(rc, 0, err)
        argv = json.loads(out)
        self.assertEqual(argv[0], "bash")
        self.assertIn("FLATSURF_ENV='flatsurf'", argv[-1])

    def test_run_refuses_outside_home(self):
        outside = os.path.join(self.lab.root, "x.py")
        with open(outside, "w") as fh:
            fh.write("\n")
        rc, out, err = self.lab.run("run", "laptop-wsl", "--dry-run", outside)
        self.assertEqual(rc, 2)
        self.assertIn("inside the lab", err)

    def test_run_experiment_off_policy_warns(self):
        rc, out, err = self.lab.run("run", "laptop-wsl", "--dry-run",
                                    "experiments/2026-09-01_e1.py")
        self.assertEqual(rc, 0)
        self.assertIn("policy.run", err)

    def test_legacy_dry_run_after_the_script_is_the_scripts_own_argument(self):
        # translate_legacy_run must only read "--dry-run" as env.py's own option when
        # it comes before the script path; one after the script is the script's own
        # argument and must reach the script, not be swallowed by env.py. "-Sage" as
        # the first token is what makes this the legacy-flags form at all.
        rc, out, err = self.lab.run("run", "-Sage", "--dry-run",
                                    "experiments/2026-09-01_e1.py", "--dry-run")
        self.assertEqual(rc, 0, err)
        cmd = json.loads(out)[-1]
        # env.py's own leading "--dry-run" was consumed (this call produced dry-run
        # JSON at all, rather than trying to shell out for real); the trailing one,
        # after the script path, survives as the script's own argument.
        self.assertIn("'experiments/2026-09-01_e1.py' '--dry-run'", cmd)


# -- the queue ----------------------------------------------------------------

E1 = "experiments/2026-09-01_e1.py"


class TestQueueLocal(EnvCase):
    def test_add_writes_a_legacy_job_file(self):
        rc, out, err = self.lab.run("queue", "add", E1, "--label", "lab:x", "--note", "n",
                                    "--args", "--bound 40")
        self.assertEqual(rc, 0, err)
        jobs = self.lab.jobs("pending")
        self.assertEqual(len(jobs), 1)
        j = jobs[0]
        self.assertRegex(j["id"], r"^\d{8}-\d{6}_2026-09-01_e1$")
        self.assertEqual(j["script"], E1)
        self.assertEqual(j["args"], ["--bound", "40"])
        self.assertEqual((j["label"], j["note"], j["status"]), ("lab:x", "n", "pending"))
        self.assertEqual(list(j)[:6], ["id", "script", "args", "label", "note", "created"])
        for k in ("started", "commit", "log", "finished", "result"):
            self.assertIsNone(j[k])
        self.assertIn("queued " + j["id"], out)
        self.assertEqual(self.lab.calls(), [], "add never talks to the remote")

    def test_add_warns_on_uncommitted(self):
        self.lab.write("experiments/2026-09-02_new.py", "print(2)\n")
        rc, out, err = self.lab.run("queue", "add", "experiments/2026-09-02_new.py")
        self.assertEqual(rc, 0, err)
        self.assertIn("uncommitted", err)

    def test_add_refuses_outside_and_duplicates(self):
        outside = os.path.join(self.lab.root, "x.py")
        with open(outside, "w") as fh:
            fh.write("\n")
        rc, out, err = self.lab.run("queue", "add", outside)
        self.assertEqual(rc, 2)
        import env
        lab = env.load_lab(self.lab.home)
        q = env.Queue(lab)
        _path, job = q.build_job(E1, [], "", "", now="20260928-101010")
        q.save(job, "pending")
        with self.assertRaises(env.EnvError):
            q.build_job(E1, [], "", "", now="20260928-101010")

    def test_add_dry_run_writes_nothing(self):
        rc, out, err = self.lab.run("queue", "add", E1, "--dry-run")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.lab.jobs("pending"), [])
        data = json.loads(out)
        self.assertTrue(data["path"].replace("\\", "/").endswith(
            "queue/pending/%s.json" % data["job"]["id"]))

    def test_list_format_is_the_legacy_one(self):
        base = {"script": E1, "label": "lab:x", "note": "a note", "created": "c",
                "status": "ok", "started": None, "commit": None, "log": None,
                "finished": None, "result": None}
        self.lab.put_job("done", dict(base, id="20260901-000000_a", args=[None]))
        self.lab.put_job("done", dict(base, id="20260901-000001_b", args=["--bound", "8"],
                                      status="exited-without-result"))
        self.lab.put_job("running", dict(base, id="20260901-000002_c", args=[],
                                         remoteState="pending", status="queued"))
        self.lab.put_job("pending", dict(base, id="20260901-000003_d", args=None,
                                         label=None, note=None, status="pending"))
        rc, out, err = self.lab.run("queue", "list")
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.split("\n"), [
            "pending  pending    20260901-000003_d  %s   []  " % E1,
            "running  pending    20260901-000002_c  %s   [lab:x]  a note" % E1,
            "done     ok         20260901-000000_a  %s   [lab:x]  a note" % E1,
            "done     exited-without-result 20260901-000001_b  %s --bound 8  [lab:x]  a note"
            % E1,
            ""])

    def test_legacy_flags(self):
        rc, out, err = self.lab.run("queue", "-Add", E1, "-Label", "lab:y",
                                    "-ScriptArgs", "--n 3")
        self.assertEqual(rc, 0, err)
        j = self.lab.jobs("pending")[0]
        self.assertEqual((j["label"], j["args"]), ("lab:y", ["--n", "3"]))
        rc, out, err = self.lab.run("queue", "-List")
        self.assertEqual(rc, 0, err)
        self.assertIn("[lab:y]", out)

    def test_unreachable_waits(self):
        self.lab.run("queue", "add", E1)
        env_ = dict(self.lab.env, ACADEMY_FAKE_PREFLIGHT="1")
        for sub in ("tick", "fetch", "status"):
            rc, out, err = self.lab.run("queue", sub, env=env_)
            self.assertEqual(rc, 1, sub)
            self.assertIn("unreachable: lingo (VPN?) -- 1 pending job(s) wait.", out)
        self.assertEqual(self.lab.calls(), [])
        rc, out, err = self.lab.run("queue", "check", env=env_)
        self.assertEqual((rc, out.strip()), (1, "unreachable: lingo (VPN?)"))


class TestQueueRemote(EnvCase):
    def add(self, script=E1, *extra):
        rc, out, err = self.lab.run("queue", "add", script, *extra)
        self.assertEqual(rc, 0, err)
        return re.search(r"queued (\S+)", out).group(1)

    def test_tick_submits_committed_and_pins_the_commit(self):
        jid = self.add(E1, "--args", "--bound 4")
        head = git(self.lab.home, "rev-parse", "HEAD").stdout.strip()
        rc, out, err = self.lab.run("queue", "tick")
        self.assertEqual(rc, 0, out + err)
        cmds = self.lab.ssh_cmds()
        self.assertEqual(cmds[0], "true")                      # reachability probe
        self.assertTrue(cmds[1].endswith("fsq version"))       # runner check
        submit = [c for c in cmds if " submit " in c]
        self.assertEqual(len(submit), 1)
        self.assertIn("'%s' '%s' '%s' '--bound' '4'" % (jid, head, E1), submit[0])
        ref = git(self.lab.bare, "rev-parse", "refs/fsq/%s" % jid).stdout.strip()
        self.assertEqual(ref, head)
        running = self.lab.jobs("running")
        self.assertEqual(len(running), 1)
        self.assertEqual(running[0]["remoteState"], "pending")
        self.assertEqual(running[0]["status"], "queued")
        self.assertEqual(running[0]["commit"], head[:7])
        self.assertEqual(self.lab.jobs("pending"), [])

    def test_tick_skips_uncommitted_and_not_in_head(self):
        self.lab.write("experiments/2026-09-02_new.py", "print(2)\n")
        jid = self.add("experiments/2026-09-02_new.py")
        with open(os.path.join(self.lab.home, E1), "a") as fh:
            fh.write("# edit\n")
        jid2 = self.add(E1)
        rc, out, err = self.lab.run("queue", "tick")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("skip (uncommitted): %s" % jid, out)
        self.assertIn("skip (uncommitted): %s" % jid2, out)
        self.assertFalse([c for c in self.lab.ssh_cmds() if " submit " in c])
        self.assertEqual(len(self.lab.jobs("pending")), 2)

    def test_tick_never_resubmits_a_known_id(self):
        jid = self.add()
        st = self.lab.state()
        st["spool"][jid] = {"state": "running", "commit": "a" * 40,
                            "submitted": "2026-09-28T09:00:00", "started": "s"}
        self.lab.set_state(st)
        rc, out, err = self.lab.run("queue", "tick")
        self.assertEqual(rc, 0, out + err)
        self.assertFalse([c for c in self.lab.ssh_cmds() if " submit " in c])
        j = self.lab.jobs("running")[0]
        self.assertEqual((j["remoteState"], j["status"], j["commit"]),
                         ("running", "running", "aaaaaaa"))

    def test_tick_refuses_a_different_runner(self):
        self.add()
        st = self.lab.state(); st["version"] = "f" * 64; self.lab.set_state(st)
        rc, out, err = self.lab.run("queue", "tick")
        self.assertEqual(rc, 1)
        self.assertIn("differs", out)
        self.assertFalse([c for c in self.lab.ssh_cmds() if " submit " in c])

    def test_fetch_collects_done_and_acks(self):
        jid = "20260928-090000_2026-09-01_e1"
        self.lab.put_job("running", {"id": jid, "script": E1, "args": [None], "label": "lab:x",
                                     "note": "", "created": "c", "status": "queued",
                                     "remoteState": "running", "started": None,
                                     "commit": "abcdef1", "log": None, "finished": None,
                                     "result": None})
        rel = "results/2026-09-01_e1.json"
        src = os.path.join(self.lab.remote_root, "fsq", "done", jid, "files", rel)
        os.makedirs(os.path.dirname(src))
        with open(src, "w") as fh:
            fh.write('{"ok": true}\n')
        st = self.lab.state()
        st["spool"][jid] = {"state": "done", "status": "ok", "exit": "0",
                            "commit": "abcdef1234", "submitted": "a", "started": "b",
                            "finished": "f", "files": [rel]}
        self.lab.set_state(st)
        rc, out, err = self.lab.run("queue", "fetch")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("fetched %s" % rel, out)
        self.assertIn("done: %s -> %s" % (jid, rel), out)
        done = self.lab.jobs("done")
        self.assertEqual(len(done), 1)
        d = done[0]
        self.assertEqual((d["status"], d["result"], d["exit"], d["finished"]),
                         ("ok", rel, "0", "f"))
        self.assertEqual(d["log"], "~/fsq/collected/%s/log" % jid)
        self.assertEqual(self.lab.state()["spool"][jid]["state"], "collected")
        with open(os.path.join(self.lab.home, rel)) as fh:
            self.assertIn("ok", fh.read())
        self.assertFalse([c for c in self.lab.ssh_cmds() if " submit " in c])

    def test_fetch_without_result_is_exited_without_result(self):
        jid = "20260928-090000_2026-09-01_e1"
        self.lab.put_job("running", {"id": jid, "script": E1, "args": [], "label": "",
                                     "note": "", "created": "c", "status": "queued",
                                     "remoteState": "running", "started": None,
                                     "commit": "abcdef1", "log": None, "finished": None,
                                     "result": None})
        st = self.lab.state()
        st["spool"][jid] = {"state": "done", "status": "ok", "exit": "0",
                            "commit": "abcdef1234", "submitted": "a", "started": "b",
                            "finished": "f", "files": []}
        self.lab.set_state(st)
        rc, out, err = self.lab.run("queue", "fetch")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.lab.jobs("done")[0]["status"], "exited-without-result")

    def test_status_and_log(self):
        jid = self.add()
        self.lab.run("queue", "tick")
        rc, out, err = self.lab.run("queue", "status")
        self.assertEqual(rc, 0, out + err)
        self.assertIn(jid, out)
        self.assertTrue(self.lab.ssh_cmds()[-1].endswith("fsq status --all"))
        rc, out, err = self.lab.run("queue", "log", jid[:15])
        self.assertEqual(rc, 0, out + err)
        self.assertIn("fsq log of %s" % jid, out)

    def test_pause_resume(self):
        rc, out, err = self.lab.run("queue", "pause")
        self.assertEqual(rc, 0, out + err)
        self.assertTrue(self.lab.state()["paused"])
        rc, out, err = self.lab.run("queue", "-Resume")
        self.assertEqual(rc, 0, out + err)
        self.assertFalse(self.lab.state()["paused"])


class TestVpn(EnvCase):
    def test_vpn_codes(self):
        for code, word in (("0", "up"), ("1", "down"), ("2", "cannot tell")):
            env_ = dict(self.lab.env, ACADEMY_FAKE_PREFLIGHT=code)
            rc, out, err = self.lab.run("vpn", env=env_)
            self.assertEqual(rc, int(code))
            self.assertIn(word, out)


# -- queue.ps1 (the PowerShell frontend itself, not just env.py underneath) ---

QUEUE_PS1 = os.path.join(SCRIPTS, "queue.ps1")
POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")


@unittest.skipUnless(POWERSHELL, "no powershell.exe on PATH")
class TestQueuePs1Frontend(EnvCase):
    """PowerShell 5.1 silently drops an empty-string element when splatting an array
    onto a native command (`& py @a`), which used to shift every argument after
    `-Label ''` or `-Note ''` by one -- the next flag's name became the label's value,
    and the real note text spilled into the script's own arguments."""

    def ps(self, *args):
        proc = subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", QUEUE_PS1] + list(args),
            capture_output=True, text=True, encoding="utf-8", env=self.lab.env,
            cwd=self.lab.home)
        return proc.returncode, proc.stdout, proc.stderr

    def test_empty_label_does_not_shift_the_note(self):
        rc, out, err = self.ps("-LabHome", self.lab.home, "-Add", "experiments/2026-09-01_e1.py",
                                "-Label", "", "-Note", "n2")
        self.assertEqual(rc, 0, out + err)
        jobs = self.lab.jobs("pending")
        self.assertEqual(len(jobs), 1, jobs)
        self.assertEqual(jobs[0]["label"], "")
        self.assertEqual(jobs[0]["note"], "n2")
        self.assertEqual(jobs[0]["args"], [])

    def test_empty_note_does_not_shift_following_script_args(self):
        rc, out, err = self.ps("-LabHome", self.lab.home, "-Add", "experiments/2026-09-01_e1.py",
                                "-Note", "", "-ScriptArgs", "--bound 40")
        self.assertEqual(rc, 0, out + err)
        jobs = self.lab.jobs("pending")
        self.assertEqual(len(jobs), 1, jobs)
        self.assertEqual(jobs[0]["note"], "")
        self.assertEqual(jobs[0]["args"], ["--bound", "40"])

    def test_non_empty_label_and_note_still_work(self):
        rc, out, err = self.ps("-LabHome", self.lab.home, "-Add", "experiments/2026-09-01_e1.py",
                                "-Label", "lab:x", "-Note", "a real note")
        self.assertEqual(rc, 0, out + err)
        jobs = self.lab.jobs("pending")
        self.assertEqual(jobs[0]["label"], "lab:x")
        self.assertEqual(jobs[0]["note"], "a real note")


if __name__ == "__main__":
    unittest.main()
