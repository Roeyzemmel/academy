#!/usr/bin/env bash
# fsq -- the FlatSurfLab job runner for a host with no scheduler (lingo).
#
# Deployed by `scripts\queue.ps1 -Deploy` to <FSQ_HOME>/bin/fsq (default ~/fsq).
# Nothing here is a daemon: a job starts when `submit` or a finishing job calls
# `dispatch`, or when the optional cron line does. The laptop only submits and fetches.
#
# Guarantees, and what provides each:
#   * at most MAX_JOBS jobs run at once (config, clamped to 1..3). A running job
#     holds an flock on one of three slot files in LOCKDIR for its whole life; the
#     kernel drops the lock when the job dies, even on kill -9, so a crash can't
#     leak a slot. The dispatcher counts held slots and never starts one past MAX_JOBS.
#   * a queue id starts at most once, ever. `submit` claims ids/<id> with mkdir,
#     which is atomic, and a claimed id is never queued again. The dispatcher moves
#     pending/<id> to running/<id> under the dispatch lock before anything runs.
#     Nothing ever moves a job back to pending.
#   * each job runs in its own git worktree wt/<id> at the job's commit. The shared
#     checkout (REPO) is never checked out by the runner, and a job's provenance
#     `dirty` flag sees only its own tree.
#   * FIFO: the dispatcher always starts the lexicographically first pending id.
#     Queue ids begin yyyyMMdd-HHmmss, so that's creation order.
#
# Spool layout under FSQ_HOME:
#   config                      REPO, PREFIX, ENV_NAME, MAX_JOBS, LOCKDIR (shell assignments)
#   ids/<id>/                   permanent "this id was accepted" marker
#   pending/<id>/ -> running/<id>/ -> done/<id>/ -> collected/<id>/
#       commit script args submitted [slot wrapper_pid job_pid started] log
#       [exit status finished files/<repo-relative path>]
#   wt/<id>/                    the job's worktree, removed at `ack`
#   checkpoints/                shared, symlinked as scratch/checkpoints in every worktree
#   paused                      when present, dispatch starts nothing
#   events.log dispatch.log
#
# Commands (all print plain text; `status` is tab-separated for queue.ps1):
#   init --repo R [--prefix P] [--max N] [--lockdir L] [--env NAME]   create the spool (paused on first init)
#   preflight [--repo R] [--prefix P] [--lockdir L] [--cron]          check every assumption; exit 1 on any FAIL
#   submit <id> <commit> <script> [args...]                           idempotent
#   dispatch                                                          start what fits; also reaps lost jobs
#   status [--all]      id state status exit commit submitted started finished files
#   log <id> [n]        tail a job's log
#   cancel <id>         pending: drop it; running: TERM its process group
#   ack <id>            done -> collected, remove the worktree and refs/fsq/<id>
#   pause | resume | set-max N | version | cron-install | cron-remove
set -uo pipefail

FSQ_SELF="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || echo "${BASH_SOURCE[0]}")"
if [ -z "${FSQ_HOME:-}" ]; then
  FSQ_HOME="$(cd "$(dirname "$FSQ_SELF")/.." && pwd)"
fi
HARD_MAX=3
CRON_TAG="# fsq-dispatch"

die() { echo "fsq: $*" >&2; exit 2; }
now() { date '+%Y-%m-%dT%H:%M:%S'; }
event() { echo "$(now) $*" >> "$FSQ_HOME/events.log"; }

clamp() {
  local n="$1"
  case "$n" in ''|*[!0-9]*) n=1 ;; esac
  [ "$n" -lt 1 ] && n=1
  [ "$n" -gt "$HARD_MAX" ] && n=$HARD_MAX
  echo "$n"
}

load_config() {
  REPO=""; PREFIX=""; ENV_NAME="flatsurf"; MAX_JOBS=1; LOCKDIR="/dev/shm/fsq-$(id -un)"
  # shellcheck disable=SC1091
  [ -f "$FSQ_HOME/config" ] && . "$FSQ_HOME/config"
  [ -n "${FSQ_LOCKDIR:-}" ] && LOCKDIR="$FSQ_LOCKDIR"
  case "$REPO" in "~/"*) REPO="$HOME/${REPO#\~/}" ;; esac
  case "$PREFIX" in "~/"*) PREFIX="$HOME/${PREFIX#\~/}" ;; esac
  MAX_JOBS=$(clamp "$MAX_JOBS")
}

need_init() {
  [ -f "$FSQ_HOME/config" ] || die "not initialised: run 'fsq init' (queue.ps1 -Deploy)"
  load_config
  mkdir -p "$LOCKDIR" || die "cannot create lock dir $LOCKDIR"
}

valid_id() { [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; }

state_of() {
  local id="$1" s
  for s in pending running done collected; do
    [ -d "$FSQ_HOME/$s/$id" ] && { echo "$s"; return; }
  done
  [ -d "$FSQ_HOME/ids/$id" ] && { echo "incomplete"; return; }
  echo "unknown"
}

# Wait until a child started with FSQ_ACK set has run far enough to be in its own
# session. Returning (and so ending the ssh session) before that can take the
# child down with it: seen under WSL, where a child of a command that exits at
# once dies before its setsid has run.
wait_ack() {
  local ack="$1" i
  for i in $(seq 1 100); do [ -e "$ack" ] && break; sleep 0.05; done
  [ -e "$ack" ] || echo "$(now) warning: no start confirmation from a detached child ($ack)" >&2
  rm -f "$ack"
}

kick() {
  # Start a dispatcher detached from this ssh session. It is gone again as soon
  # as it has started what fits.
  [ "${FSQ_NO_KICK:-0}" = "1" ] && return 0
  local ack="$FSQ_HOME/.ack.kick.$$.$RANDOM"
  FSQ_ACK="$ack" setsid nohup "$FSQ_SELF" dispatch </dev/null >>"$FSQ_HOME/dispatch.log" 2>&1 &
  wait_ack "$ack"
}

# ---------------------------------------------------------------- init/config

cmd_init() {
  local repo="" prefix="" max="" lockdir="" envname=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --repo) repo="$2"; shift 2 ;;
      --prefix) prefix="$2"; shift 2 ;;
      --max) max="$2"; shift 2 ;;
      --lockdir) lockdir="$2"; shift 2 ;;
      --env) envname="$2"; shift 2 ;;
      *) die "init: unknown option $1" ;;
    esac
  done
  local first=0
  [ -f "$FSQ_HOME/config" ] || first=1
  load_config
  [ -n "$repo" ] && REPO="$repo"
  [ -n "$prefix" ] && PREFIX="$prefix"
  [ -n "$max" ] && MAX_JOBS=$(clamp "$max")
  [ -n "$lockdir" ] && LOCKDIR="$lockdir"
  [ -n "$envname" ] && ENV_NAME="$envname"
  [ -n "$REPO" ] || die "init: --repo is required"
  mkdir -p "$FSQ_HOME"/{bin,ids,pending,running,done,collected,wt,checkpoints} || die "cannot create $FSQ_HOME"
  write_config
  # A fresh spool starts paused, so deploying starts nothing. `resume` opens it.
  [ "$first" = 1 ] && touch "$FSQ_HOME/paused"
  event "init repo=$REPO max=$MAX_JOBS lockdir=$LOCKDIR"
  echo "initialised $FSQ_HOME (max $MAX_JOBS, lock dir $LOCKDIR)$([ -e "$FSQ_HOME/paused" ] && echo ', paused')"
}

write_config() {
  local tmp="$FSQ_HOME/config.tmp.$$"
  {
    printf 'REPO=%q\n' "$REPO"
    printf 'PREFIX=%q\n' "$PREFIX"
    printf 'ENV_NAME=%q\n' "$ENV_NAME"
    printf 'MAX_JOBS=%q\n' "$MAX_JOBS"
    printf 'LOCKDIR=%q\n' "$LOCKDIR"
  } > "$tmp" && mv "$tmp" "$FSQ_HOME/config"
}

cmd_set_max() {
  need_init
  local asked="${1:-}" got
  got=$(clamp "$asked")
  MAX_JOBS=$got; write_config
  [ "$asked" != "$got" ] && echo "fsq: $asked clamped to $got (allowed 1..$HARD_MAX)" >&2
  event "set-max $got"
  echo "max $got"
  kick
}

cmd_pause() { need_init; touch "$FSQ_HOME/paused"; event pause; echo paused; }
cmd_resume() { need_init; rm -f "$FSQ_HOME/paused"; event resume; echo resumed; kick; }
cmd_version() { sha256sum "$FSQ_SELF" | cut -d' ' -f1; }

# --------------------------------------------------------------------- submit

cmd_submit() {
  # Test hook: an ssh session that dropped before the remote side did anything.
  [ "${FSQ_FAULT:-}" = "presubmit" ] && exit 255
  [ $# -ge 3 ] || die "usage: submit <id> <commit> <script> [args...]"
  local id="$1" commit="$2" script="$3"; shift 3
  valid_id "$id" || die "bad id '$id'"
  need_init
  if [ -d "$FSQ_HOME/ids/$id" ]; then
    echo "exists $id $(state_of "$id")"
    kick; return 0
  fi
  local full
  full=$(git -C "$REPO" rev-parse --verify -q "$commit^{commit}") || die "commit $commit is not in $REPO (push it first)"
  git -C "$REPO" cat-file -e "$full:$script" 2>/dev/null || die "$script is not in commit $full"
  local tmp="$FSQ_HOME/pending/.new.$id.$$"
  mkdir "$tmp" || die "cannot write $tmp"
  echo "$full" > "$tmp/commit"
  printf '%s\n' "$script" > "$tmp/script"
  { [ $# -gt 0 ] && printf '%q ' "$@"; echo; } > "$tmp/args"
  now > "$tmp/submitted"
  # The claim. mkdir either creates the marker or fails because it exists, and
  # only the process that created it may queue the job.
  if ! mkdir "$FSQ_HOME/ids/$id" 2>/dev/null; then
    rm -rf "$tmp"
    echo "exists $id $(state_of "$id")"
    kick; return 0
  fi
  mv "$tmp" "$FSQ_HOME/pending/$id" || die "claimed $id but could not queue it; see $tmp"
  event "submit $id ${full:0:7} $script"
  echo "submitted $id ${full:0:7}"
  kick
  if [ "${FSQ_FAULT:-}" = "submit" ]; then
    # Test hook: behave like an ssh session that dropped after the remote side
    # acted, which is what caused the 2026-09-20 double launch.
    exit 255
  fi
}

# ------------------------------------------------------------------- dispatch

# Try every slot. Leaves SLOT and SLOT_FD set (lock held) and returns 0 when a
# slot is free and fewer than MAX_JOBS are held; otherwise holds nothing.
acquire_slot() {
  local k fd busy=0 free="" freefd=""
  for k in $(seq 1 "$HARD_MAX"); do
    exec {fd}>>"$LOCKDIR/slot.$k"
    if flock -n "$fd"; then
      if [ -z "$free" ]; then free=$k; freefd=$fd; else exec {fd}>&-; fi
    else
      busy=$((busy + 1)); exec {fd}>&-
    fi
  done
  if [ -n "$free" ] && [ "$busy" -lt "$MAX_JOBS" ]; then
    SLOT=$free; SLOT_FD=$freefd; return 0
  fi
  [ -n "$freefd" ] && exec {freefd}>&-
  return 1
}

first_pending() {
  local p
  for p in $(cd "$FSQ_HOME/pending" && LC_ALL=C ls -1); do
    case "$p" in .*) continue ;; esac
    echo "$p"; return 0
  done
  return 1
}

# running/<id> -> done/<id>: copy what the job wrote under results/ out of its
# worktree, record the exit code and status.
finalize() {
  local id="$1" rc="$2" st="$3" d="$FSQ_HOME/running/$1" wt="$FSQ_HOME/wt/$1" f
  [ -d "$d" ] || return 0
  if [ -d "$wt" ]; then
    while IFS= read -r -d '' f; do
      mkdir -p "$d/files/$(dirname "$f")"
      cp -p "$wt/$f" "$d/files/$f"
    done < <(git -C "$wt" ls-files -z -o -m --exclude-standard -- results 2>/dev/null)
  fi
  echo "$rc" > "$d/exit"
  echo "$st" > "$d/status"
  now > "$d/finished"
  mv "$d" "$FSQ_HOME/done/$id"
  event "finish $id $st exit=$rc"
}

# A running job whose slot is free has lost its wrapper and its process (reboot,
# kill -9). Record it as lost; never restart it.
reap() {
  local d id slot fd jp
  for d in "$FSQ_HOME"/running/*/; do
    [ -d "$d" ] || continue
    id=$(basename "$d")
    slot=$(cat "$d/slot" 2>/dev/null) || continue
    exec {fd}>>"$LOCKDIR/slot.$slot"
    if flock -n "$fd"; then
      if [ -d "$FSQ_HOME/running/$id" ]; then
        jp=$(cat "$FSQ_HOME/running/$id/job_pid" 2>/dev/null || true)
        if [ -n "$jp" ] && kill -0 "$jp" 2>/dev/null; then
          echo "$(now) warning: $id holds no slot lock but pid $jp is alive; left running" >&2
        else
          finalize "$id" "?" lost
        fi
      fi
    fi
    exec {fd}>&-
  done
}

cmd_dispatch() {
  need_init
  local dl id d ack
  exec {dl}>>"$LOCKDIR/dispatch.lock"
  # Blocking with a timeout, not -n: a dispatcher that is just finishing may
  # already have scanned pending/, so a second one must wait and rescan.
  flock -w 300 "$dl" || { echo "$(now) dispatch lock busy for 300s; giving up" >&2; return 0; }
  reap
  while [ ! -e "$FSQ_HOME/paused" ]; do
    id=$(first_pending) || break
    acquire_slot || break
    d="$FSQ_HOME/running/$id"
    mv "$FSQ_HOME/pending/$id" "$d" || { exec {SLOT_FD}>&-; break; }
    echo "$SLOT" > "$d/slot"
    event "claim $id slot=$SLOT"
    if ! git -C "$REPO" worktree add -q --detach "$FSQ_HOME/wt/$id" "$(cat "$d/commit")" >>"$d/log" 2>&1; then
      finalize "$id" "?" setup-failed
      exec {SLOT_FD}>&-
      continue
    fi
    mkdir -p "$FSQ_HOME/wt/$id/scratch"
    ln -sfn "$FSQ_HOME/checkpoints" "$FSQ_HOME/wt/$id/scratch/checkpoints"
    # The wrapper inherits the slot lock (SLOT_FD); the dispatch lock is closed
    # for it, or every job would hold up every later dispatcher.
    ack="$FSQ_HOME/.ack.run.$id"
    FSQ_ACK="$ack" FSQ_SLOT_FD=$SLOT_FD setsid "$FSQ_SELF" _run "$id" </dev/null >>"$FSQ_HOME/dispatch.log" 2>&1 {dl}>&- &
    exec {SLOT_FD}>&-
    wait_ack "$ack"
  done
  exec {dl}>&-
}

cmd__run() {
  local id="$1" fd="${FSQ_SLOT_FD:-}"
  load_config
  local d="$FSQ_HOME/running/$id" wt="$FSQ_HOME/wt/$id"
  [ -d "$d" ] || { echo "$(now) _run: $id is not running" >&2; exit 1; }
  if [ -z "$fd" ] || ! flock -n "$fd" 2>/dev/null; then
    # Never run without the slot: that would break the cap.
    finalize "$id" "?" setup-failed
    exit 1
  fi
  echo $$ > "$d/wrapper_pid"
  now > "$d/started"
  event "start $id slot=$(cat "$d/slot")"
  local script jp rc st
  script=$(cat "$d/script")
  eval "set -- $(cat "$d/args")"
  echo "== fsq $(now) start $id on $(hostname) slot $(cat "$d/slot"): commit $(cut -c1-12 "$d/commit") $script $(cat "$d/args")" >> "$d/log"
  local envs=(PYTHONUNBUFFERED=1 FLATSURF_ENV="$ENV_NAME")
  [ -n "$PREFIX" ] && envs+=(MINIFORGE_PREFIX="$PREFIX")
  # setsid: the job gets its own process group, which is what `cancel` kills.
  ( cd "$wt" || exit 97; exec setsid env "${envs[@]}" bash scripts/run.sh "$script" "$@" ) \
      >>"$d/log" 2>&1 </dev/null &
  jp=$!
  echo "$jp" > "$d/job_pid"
  wait "$jp"; rc=$?
  st=ok
  [ "$rc" -ne 0 ] && st=failed
  [ -e "$d/cancel" ] && st=cancelled
  echo "== fsq $(now) end $id: exit $rc ($st)" >> "$d/log"
  finalize "$id" "$rc" "$st"
  # Release the slot, then chain to the next job.
  exec {fd}>&-
  exec "$FSQ_SELF" dispatch
}

# ------------------------------------------------------------ inspect / manage

field() { cat "$1" 2>/dev/null | head -n1 | tr -d '\t\r'; }

cmd_status() {
  need_init
  local all=0 m id st d files
  [ "${1:-}" = "--all" ] && all=1
  [ -e "$FSQ_HOME/paused" ] && echo "#paused"
  echo "#max	$MAX_JOBS"
  for m in "$FSQ_HOME"/ids/*/; do
    [ -d "$m" ] || continue
    id=$(basename "$m"); st=$(state_of "$id")
    [ "$st" = collected ] && [ "$all" = 0 ] && continue
    d="$FSQ_HOME/$st/$id"
    files=""
    [ -d "$d/files" ] && files=$(cd "$d/files" && find . -type f | sed 's|^\./||' | LC_ALL=C sort | paste -sd, -)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$st" \
      "$(field "$d/status")" "$(field "$d/exit")" "$(field "$d/commit")" \
      "$(field "$d/submitted")" "$(field "$d/started")" "$(field "$d/finished")" "$files"
  done
}

cmd_log() {
  need_init
  local id="$1" n="${2:-40}" st
  st=$(state_of "$id")
  [ -f "$FSQ_HOME/$st/$id/log" ] || die "no log for $id ($st)"
  tail -n "$n" "$FSQ_HOME/$st/$id/log"
}

cmd_cancel() {
  need_init
  local id="$1" dl jp
  exec {dl}>>"$LOCKDIR/dispatch.lock"
  flock -w 60 "$dl" || die "dispatch lock busy"
  case "$(state_of "$id")" in
    pending)
      mv "$FSQ_HOME/pending/$id" "$FSQ_HOME/running/$id" && finalize "$id" "?" cancelled
      echo "cancelled $id (was pending)" ;;
    running)
      touch "$FSQ_HOME/running/$id/cancel"
      jp=$(cat "$FSQ_HOME/running/$id/job_pid" 2>/dev/null || true)
      [ -n "$jp" ] && kill -TERM -- "-$jp" 2>/dev/null
      echo "cancel requested for $id (TERM to process group ${jp:-?})" ;;
    *) echo "nothing to cancel: $id is $(state_of "$id")" ;;
  esac
  exec {dl}>&-
}

cmd_ack() {
  need_init
  local id="$1"
  [ "$(state_of "$id")" = done ] || { echo "not done: $id is $(state_of "$id")"; return 0; }
  git -C "$REPO" worktree remove --force "$FSQ_HOME/wt/$id" >/dev/null 2>&1 || rm -rf "$FSQ_HOME/wt/$id"
  git -C "$REPO" worktree prune >/dev/null 2>&1
  git -C "$REPO" update-ref -d "refs/fsq/$id" >/dev/null 2>&1
  mv "$FSQ_HOME/done/$id" "$FSQ_HOME/collected/$id"
  event "ack $id"
  echo "acked $id"
}

cmd_cron_install() {
  need_init
  local line1="*/10 * * * * $FSQ_SELF dispatch >>$FSQ_HOME/dispatch.log 2>&1 $CRON_TAG"
  local line2="@reboot $FSQ_SELF dispatch >>$FSQ_HOME/dispatch.log 2>&1 $CRON_TAG"
  { crontab -l 2>/dev/null | grep -vF "$CRON_TAG" || true; echo "$line1"; echo "$line2"; } | crontab - \
    || die "crontab refused"
  echo "cron installed:"; crontab -l | grep -F "$CRON_TAG"
}

cmd_cron_remove() {
  { crontab -l 2>/dev/null | grep -vF "$CRON_TAG" || true; } | crontab - || die "crontab refused"
  echo "cron lines removed"
}

# ------------------------------------------------------------------ preflight

cmd_preflight() {
  local repo="" prefix="" lockdir="" cron=0 fail=0 envname="flatsurf"
  while [ $# -gt 0 ]; do
    case "$1" in
      --repo) repo="$2"; shift 2 ;;
      --prefix) prefix="$2"; shift 2 ;;
      --lockdir) lockdir="$2"; shift 2 ;;
      --env) envname="$2"; shift 2 ;;
      --cron) cron=1; shift ;;
      *) die "preflight: unknown option $1" ;;
    esac
  done
  case "$repo" in "~/"*) repo="$HOME/${repo#\~/}" ;; esac
  case "$prefix" in "~/"*) prefix="$HOME/${prefix#\~/}" ;; esac
  [ -n "$lockdir" ] || lockdir="${FSQ_LOCKDIR:-/dev/shm/fsq-$(id -un)}"
  ok()   { echo "PASS  $*"; }
  bad()  { echo "FAIL  $*"; fail=1; }
  note() { echo "INFO  $*"; }

  # A1 bash with {fd} redirections (4.1+)
  if [ "${BASH_VERSINFO[0]}" -ge 5 ] || { [ "${BASH_VERSINFO[0]}" -eq 4 ] && [ "${BASH_VERSINFO[1]}" -ge 1 ]; }; then
    ok "A1 bash $BASH_VERSION"; else bad "A1 bash $BASH_VERSION is older than 4.1"; fi
  # A2 userland tools
  local t missing=""
  for t in flock setsid nohup git sha256sum seq find paste; do
    command -v "$t" >/dev/null 2>&1 || missing="$missing $t"
  done
  [ -z "$missing" ] && ok "A2 tools present (flock setsid nohup git sha256sum seq find paste)" || bad "A2 missing:$missing"
  # A3 git with `worktree remove` (2.17+)
  local gv; gv=$(git --version 2>/dev/null | awk '{print $3}')
  if printf '2.17\n%s\n' "$gv" | sort -V -C 2>/dev/null; then ok "A3 git $gv"; else bad "A3 git $gv is older than 2.17"; fi
  # A4 the lock dir: writable, local, and flock actually excludes
  if mkdir -p "$lockdir" 2>/dev/null && [ -w "$lockdir" ]; then
    local fstype; fstype=$(stat -f -c %T "$lockdir" 2>/dev/null)
    case "$fstype" in
      nfs*|cifs|smb*|fuse*|9p|v9fs) bad "A4 lock dir $lockdir is on $fstype; it must be a local filesystem" ;;
      *) ok "A4 lock dir $lockdir writable ($fstype)" ;;
    esac
    local lf="$lockdir/preflight.$$" pf="" tries=0
    rm -f "$lf.ready"
    # The holder says when it has the lock; only then does the second process try.
    ( exec 8>>"$lf"; flock -w 5 8 && touch "$lf.ready" && sleep 2 ) </dev/null >/dev/null 2>&1 &
    pf=$!
    while [ ! -e "$lf.ready" ] && [ $tries -lt 50 ]; do sleep 0.1; tries=$((tries + 1)); done
    if [ ! -e "$lf.ready" ]; then
      bad "A5 could not take a lock in $lockdir at all"
    elif ( exec 9>>"$lf"; flock -n 9 ) </dev/null 2>/dev/null; then
      bad "A5 flock did not exclude a second process in $lockdir"
    else
      ok "A5 flock excludes a second process in $lockdir"
    fi
    wait "$pf" 2>/dev/null
    rm -f "$lf.ready"
    local tl=0
    ( exec 9>>"$lf"; flock -n 9 ) </dev/null 2>/dev/null && tl=1
    [ $tl = 1 ] && ok "A6 lock released when its holder exits" || bad "A6 lock still held after its holder exited"
    rm -f "$lf"
  else
    bad "A4 cannot create or write lock dir $lockdir"
  fi
  # A7 the spool: writable, headroom
  if mkdir -p "$FSQ_HOME" 2>/dev/null && [ -w "$FSQ_HOME" ]; then
    local avail; avail=$(df -Pk "$FSQ_HOME" | awk 'NR==2 {print int($4/1024)}')
    ok "A7 spool $FSQ_HOME writable (${avail} MB free on its filesystem; quota is checked by A8)"
  else
    bad "A7 cannot write spool $FSQ_HOME"
  fi
  if command -v quota >/dev/null 2>&1; then
    note "A8 quota: $(quota -s 2>/dev/null </dev/null | tail -n +3 | tr -s ' ' | paste -sd' ' -)"
  else
    note "A8 no quota command; check the home quota by hand"
  fi
  # A9 the repo
  if [ -n "$repo" ] && git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
    ok "A9 repo $repo is a git repository"
    local wtl; wtl=$(git -C "$repo" worktree list 2>/dev/null | wc -l)
    note "A9 worktrees now: $wtl"
  else
    bad "A9 repo '$repo' is not a git repository"
  fi
  # A10 the env
  if [ -n "$prefix" ]; then
    if [ -x "$prefix/envs/$envname/bin/python" ]; then ok "A10 env $prefix/envs/$envname"; else bad "A10 no python in $prefix/envs/$envname"; fi
  else
    note "A10 no prefix given; run.sh will default to ~/miniforge3"
  fi
  # A11 detached processes outlive the ssh session
  local kup; kup=$(grep -hE '^[[:space:]]*KillUserProcesses' /etc/systemd/logind.conf /etc/systemd/logind.conf.d/*.conf 2>/dev/null | tail -n1)
  case "$kup" in *[Yy][Ee][Ss]*) bad "A11 logind has $kup: detached jobs die at logout" ;; *) ok "A11 logind KillUserProcesses not set to yes (${kup:-default})" ;; esac
  # A12 cron, only if asked for
  if [ "$cron" = 1 ]; then
    # Capture, don't pipe: under pipefail, `crontab -l | grep` fails on a user with no
    # crontab (crontab -l exits 1) even when grep matches "no crontab".
    local ctab
    if command -v crontab >/dev/null 2>&1 && { ctab=$(crontab -l 2>&1) || [[ "$ctab" == *[Nn]o\ crontab* ]]; }; then
      ok "A12 crontab usable"
    else
      bad "A12 crontab not usable"
    fi
  fi
  # Informational: other schedulers, other jobs, load
  for t in sbatch tsp at; do command -v "$t" >/dev/null 2>&1 && note "I1 $t exists here; consider it instead"; done
  local legacy; legacy=$(pgrep -u "$(id -un)" -f '[s]cripts/run.sh' | tr '\n' ' ')
  [ -n "$legacy" ] && note "I2 jobs running outside fsq (not counted by the cap): pids $legacy" || note "I2 no jobs running outside fsq"
  note "I3 nproc $(nproc 2>/dev/null), $(uptime | sed 's/.*load/load/')"
  [ "$fail" = 0 ] && echo "preflight: all checks passed" || echo "preflight: FAILED"
  return $fail
}

# ------------------------------------------------------------------------ main

main() {
  local cmd="${1:-}"; [ $# -gt 0 ] && shift
  # A detached child confirms it is running (see wait_ack); its children must not.
  if [ -n "${FSQ_ACK:-}" ]; then touch "$FSQ_ACK"; unset FSQ_ACK; fi
  case "$cmd" in
    init) cmd_init "$@" ;;
    preflight) cmd_preflight "$@" ;;
    submit) cmd_submit "$@" ;;
    dispatch) cmd_dispatch ;;
    _run) cmd__run "$@" ;;
    status) cmd_status "$@" ;;
    log) cmd_log "$@" ;;
    cancel) cmd_cancel "$@" ;;
    ack) cmd_ack "$@" ;;
    pause) cmd_pause ;;
    resume) cmd_resume ;;
    set-max) cmd_set_max "$@" ;;
    version) cmd_version ;;
    cron-install) cmd_cron_install ;;
    cron-remove) cmd_cron_remove ;;
    ""|-h|--help|help) sed -n '2,45p' "$FSQ_SELF" ;;
    *) die "unknown command '$cmd' (try: fsq help)" ;;
  esac
}
main "$@"
