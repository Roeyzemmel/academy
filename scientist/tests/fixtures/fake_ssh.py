"""A stand-in for ``ssh`` and ``scp`` in the env.py tests: no network, no remote.

Invoked as ``py fake_ssh.py [ssh options] HOST COMMAND...`` (ssh mode) or
``py fake_ssh.py --scp [-q] SRC DEST`` (scp mode). It emulates the part of the fsq
runner protocol that env.py speaks (``version``, ``status [--all]``, ``submit``,
``ack``, ``log``, ``pause``, ``resume``) against a JSON state file, and records every
call in a log so the tests can assert what was (and was not) sent.

Environment:
  FAKE_SSH_STATE   the state file: {"reachable": bool, "version": str, "paused": bool,
                   "max": int, "spool": {id: {state, status, exit, commit, submitted,
                   started, finished, files, args}}, "fail": {"<sub>": rc}}
  FAKE_SSH_LOG     one JSON line per call: {"mode": "ssh"|"scp", "host", "cmd"/"args"}
  FAKE_REMOTE_ROOT scp reads "host:<path>" from <root>/<path> (a leading ~/ dropped)
"""

import json
import os
import shlex
import shutil
import sys


def log(entry):
    with open(os.environ["FAKE_SSH_LOG"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def load():
    with open(os.environ["FAKE_SSH_STATE"], "r", encoding="utf-8") as fh:
        return json.load(fh)


def save(state):
    with open(os.environ["FAKE_SSH_STATE"], "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1)


def scp(argv):
    args = [a for a in argv if a != "-q"]
    src, dest = args[0], args[1]
    log({"mode": "scp", "args": args})
    state = load()
    if not state.get("reachable", True):
        return 1
    if ":" in src and not os.path.isabs(src):
        path = src.split(":", 1)[1]
        if path.startswith("~/"):
            path = path[2:]
        full = os.path.join(os.environ["FAKE_REMOTE_ROOT"], path)
        if not os.path.isfile(full):
            print("scp: %s: No such file or directory" % path, file=sys.stderr)
            return 1
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        shutil.copyfile(full, dest)
        return 0
    path = dest.split(":", 1)[1]
    if path.startswith("~/"):
        path = path[2:]
    full = os.path.join(os.environ["FAKE_REMOTE_ROOT"], path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    shutil.copyfile(src, full)
    return 0


def ssh(argv):
    i = 0
    while i < len(argv) and argv[i].startswith("-"):
        i += 2 if argv[i] in ("-o", "-p", "-i", "-l") else 1
    host, cmd = argv[i], " ".join(argv[i + 1:])
    log({"mode": "ssh", "host": host, "cmd": cmd})
    state = load()
    if not state.get("reachable", True):
        print("ssh: connect to host %s port 22: Connection timed out" % host, file=sys.stderr)
        return 255
    print("** WARNING: connection is not using a post-quantum key exchange algorithm.",
          file=sys.stderr)
    words = shlex.split(cmd)
    while words and "=" in words[0] and not words[0].startswith(("/", "~")):
        words.pop(0)                                     # env assignments
    if words == ["true"]:
        return 0
    if not words or not words[0].endswith("/bin/fsq"):
        print("fake ssh: unsupported command %r" % cmd, file=sys.stderr)
        return 127
    sub, rest = words[1], words[2:]
    rc = (state.get("fail") or {}).get(sub)
    spool = state.setdefault("spool", {})
    if sub == "version":
        print(state.get("version", ""))
    elif sub == "status":
        if state.get("paused"):
            print("#paused")
        print("#max\t%s" % state.get("max", 1))
        for jid in sorted(spool):
            r = spool[jid]
            if r["state"] == "collected" and rest != ["--all"]:
                continue
            print("\t".join([jid, r["state"], r.get("status", ""), str(r.get("exit", "")),
                             r.get("commit", ""), r.get("submitted", ""),
                             r.get("started", ""), r.get("finished", ""),
                             ",".join(r.get("files", []))]))
    elif sub == "submit":
        jid, commit, script = rest[:3]
        if jid in spool:
            print("exists %s %s" % (jid, spool[jid]["state"]))
        else:
            spool[jid] = {"state": "pending", "commit": commit, "script": script,
                          "args": rest[3:], "submitted": "2026-09-28T10:00:00"}
            print("submitted %s %s" % (jid, commit[:7]))
    elif sub == "ack":
        jid = rest[0]
        if jid in spool and spool[jid]["state"] == "done":
            spool[jid]["state"] = "collected"
            print("acked %s" % jid)
        else:
            print("not done: %s" % jid)
    elif sub == "log":
        print("== fsq log of %s (%s lines)" % (rest[0], rest[1] if len(rest) > 1 else 40))
    elif sub in ("pause", "resume"):
        state["paused"] = sub == "pause"
        print("paused" if sub == "pause" else "resumed")
    else:
        print("fake fsq: unsupported %s" % sub, file=sys.stderr)
        return 2
    save(state)
    return rc or 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--scp"]:
        sys.exit(scp(sys.argv[2:]))
    sys.exit(ssh(sys.argv[1:]))
