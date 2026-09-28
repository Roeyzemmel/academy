#!/usr/bin/env bash
# Local test of scripts/fsq.sh with fake sleep jobs. Run it in WSL or any Linux
# shell, never on lingo:
#
#   bash scripts/test_fsq.sh [workdir]
#
# It builds a throwaway git repo standing in for ~/FlatSurfLab, a spool standing
# in for ~/fsq, and a lock dir under /dev/shm, then checks:
#   cap     at most MAX_JOBS jobs overlap (1, 2, and 9 clamped to 3)
#   once    a repeated or concurrent submit of one id starts it exactly once,
#           including after a submit whose "ssh" failed (exit 255) after acting
#   fifo    jobs start in queue-id order
#   tree    each job runs at its own commit in its own worktree; another job's
#           result file does not make its provenance dirty; the shared checkout
#           is never moved
#   lost    a job killed with its wrapper is recorded as lost, not restarted
#   cancel  pending and running jobs can be cancelled
#   pause   a paused spool starts nothing
#   idle    no fsq process is left running once the queue drains
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FSQ_SRC="$HERE/fsq.sh"
W="${1:-$(mktemp -d)}"
rm -rf "$W"; mkdir -p "$W"
W="$(cd "$W" && pwd)"
export FSQ_HOME="$W/fsq"
export FSQ_LOCKDIR="/dev/shm/fsq-test-$$"
export FSQ_TEST_TRACE="$W/trace.log"
REPO="$W/repo"
FSQ="$FSQ_HOME/bin/fsq"
PASS=0; FAIL=0

ok()  { echo "  PASS $*"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL $*"; FAIL=$((FAIL + 1)); }
check() { if eval "$1"; then ok "$2"; else bad "$2  [$1]"; fi; }

cleanup() {
  pkill -f "$FSQ_HOME/bin/fsq" 2>/dev/null
  rm -rf "$FSQ_LOCKDIR"
}
trap cleanup EXIT

# --- a fake ~/FlatSurfLab ----------------------------------------------------
mkdir -p "$REPO/scripts" "$REPO/experiments" "$REPO/results"
cd "$REPO" || exit 1
git init -q .
git config user.email test@example.invalid; git config user.name test
cat > scripts/run.sh <<'EOF'
#!/usr/bin/env bash
# Stand-in for the real run.sh: no conda, just run the script with bash.
cd "$(dirname "${BASH_SOURCE[0]}")/.." && exec bash "$@"
EOF
cat > experiments/job.sh <<'EOF'
#!/usr/bin/env bash
# job.sh NAME SECONDS [touch-tracked]
name=$1; secs=$2
dirty=0; git diff --quiet HEAD || dirty=1
echo "start $name $(date +%s.%N) head=$(git rev-parse --short HEAD) dirty=$dirty ver=$(cat version.txt) cwd=$PWD" >> "$FSQ_TEST_TRACE"
[ "${3:-}" = touch-tracked ] && echo "{\"by\":\"$name\"}" > results/tracked.json
sleep "$secs"
echo "{\"name\":\"$name\"}" > "results/$name.json"
echo "end $name $(date +%s.%N)" >> "$FSQ_TEST_TRACE"
EOF
echo v1 > version.txt
echo '{}' > results/tracked.json
git add -A && git commit -qm c1
C1=$(git rev-parse HEAD)

mkdir -p "$FSQ_HOME/bin"; cp "$FSQ_SRC" "$FSQ"; chmod +x "$FSQ"
"$FSQ" init --repo "$REPO" --max 1 >/dev/null
"$FSQ" resume >/dev/null

# --- helpers -----------------------------------------------------------------
n_in() { find "$FSQ_HOME/$1" -mindepth 1 -maxdepth 1 -type d ! -name '.*' | wc -l; }
wait_idle() {  # wait until nothing pending or running, up to $1 seconds
  local t=0 lim=${1:-120}
  while [ $((t)) -lt $((lim * 10)) ]; do
    [ "$(n_in pending)" = 0 ] && [ "$(n_in running)" = 0 ] && return 0
    sleep 0.1; t=$((t + 1))
  done
  echo "  (timed out waiting for idle)"; return 1
}
max_overlap() {  # over the trace lines for names matching $1
  grep -E "^(start|end) $1 " "$FSQ_TEST_TRACE" | awk '{print $3, ($1=="start") ? 1 : -1}' \
    | sort -k1,1g -k2,2n | awk '{c += $2; if (c > m) m = c} END {print m + 0}'
}
starts_of() { grep -c "^start $1 " "$FSQ_TEST_TRACE"; }
start_order() { grep -E "^start $1" "$FSQ_TEST_TRACE" | awk '{print $2}' | paste -sd' ' -; }
submit() { "$FSQ" submit "$@"; }
ack_all() { for d in "$FSQ_HOME"/done/*/; do [ -d "$d" ] && "$FSQ" ack "$(basename "$d")" >/dev/null; done; }
: > "$FSQ_TEST_TRACE"

echo "== cap: MAX_JOBS=1, four 1-second jobs submitted at once"
for i in 1 2 3 4; do submit "20260101-00000${i}_capA$i" "$C1" experiments/job.sh "capA$i" 1 >/dev/null; done
sleep 0.5
echo "  running right after submit: $(n_in running), pending: $(n_in pending)"
wait_idle 60
check '[ "$(max_overlap "capA[0-9]")" = 1 ]' "max overlap is $(max_overlap 'capA[0-9]') (want 1)"
check '[ "$(n_in done)" = 4 ]' "all 4 done"
ack_all

echo "== cap: MAX_JOBS=2, five 3-second jobs"
"$FSQ" set-max 2 >/dev/null
for i in 1 2 3 4 5; do submit "20260101-00001${i}_capB$i" "$C1" experiments/job.sh "capB$i" 3 >/dev/null; done
wait_idle 60
check '[ "$(max_overlap "capB[0-9]")" = 2 ]' "max overlap is $(max_overlap 'capB[0-9]') (want 2)"
ack_all

echo "== cap: set-max 9 is clamped to 3, six 4-second jobs"
out=$("$FSQ" set-max 9 2>&1); echo "  set-max 9 says: $(echo "$out" | paste -sd' ' -)"
check 'grep -q "^MAX_JOBS=3$" "$FSQ_HOME/config"' "config holds MAX_JOBS=3"
sed -i 's/^MAX_JOBS=.*/MAX_JOBS=7/' "$FSQ_HOME/config"   # a hand edit past the limit
for i in 1 2 3 4 5 6; do submit "20260101-00002${i}_capC$i" "$C1" experiments/job.sh "capC$i" 4 >/dev/null; done
wait_idle 60
check '[ "$(max_overlap "capC[0-9]")" = 3 ]' "max overlap is $(max_overlap 'capC[0-9]') with MAX_JOBS=7 in config (want 3)"
ack_all
"$FSQ" set-max 1 >/dev/null

echo "== once: a submit whose ssh 'failed' after acting, then the retry"
FSQ_FAULT=submit "$FSQ" submit 20260101-000100_onceA "$C1" experiments/job.sh onceA 2 >/dev/null
rc=$?
echo "  first submit exit code: $rc (the old queue.ps1 would have treated this as 'not started')"
sleep 0.3
out=$(submit 20260101-000100_onceA "$C1" experiments/job.sh onceA 2)
echo "  retry says: $out"
check '[ "$rc" = 255 ]' "fault hook made the first submit exit 255"
check 'echo "$out" | grep -q "^exists 20260101-000100_onceA"' "retry reports the job exists"
echo "== once: ten concurrent submits of one new id"
for k in $(seq 1 10); do submit 20260101-000101_onceB "$C1" experiments/job.sh onceB 1 >/dev/null & done
wait
wait_idle 60
check '[ "$(starts_of onceA)" = 1 ]' "onceA started $(starts_of onceA) time(s)"
check '[ "$(starts_of onceB)" = 1 ]' "onceB started $(starts_of onceB) time(s)"
out=$(submit 20260101-000100_onceA "$C1" experiments/job.sh onceA 2); sleep 1
check 'echo "$out" | grep -q "exists 20260101-000100_onceA done"' "a submit after it finished is refused ($out)"
ack_all
out=$(submit 20260101-000100_onceA "$C1" experiments/job.sh onceA 2); sleep 1
check '[ "$(starts_of onceA)" = 1 ]' "and after ack too ($out); still $(starts_of onceA) start"

echo "== fifo: MAX_JOBS=1, a blocker, then ids submitted out of order"
submit 20260101-000200_fifo0 "$C1" experiments/job.sh fifo0 2 >/dev/null
sleep 0.3
for i in 4 2 5 1 3; do submit "20260101-00020${i}_fifo$i" "$C1" experiments/job.sh "fifo$i" 0.2 >/dev/null; done
wait_idle 60
order=$(start_order fifo)
check '[ "$order" = "fifo0 fifo1 fifo2 fifo3 fifo4 fifo5" ]' "start order: $order"
ack_all

echo "== tree: two jobs at two commits, one modifying a tracked result"
"$FSQ" set-max 2 >/dev/null
submit 20260101-000300_treeA "$C1" experiments/job.sh treeA 3 touch-tracked >/dev/null
echo v2 > version.txt; git commit -qam c2; C2=$(git rev-parse HEAD)
git checkout -q "$C1"          # the shared checkout sits somewhere else entirely
sleep 1
submit 20260101-000301_treeB "$C2" experiments/job.sh treeB 1 >/dev/null
wait_idle 60
la=$(grep '^start treeA ' "$FSQ_TEST_TRACE"); lb=$(grep '^start treeB ' "$FSQ_TEST_TRACE")
echo "  $la"; echo "  $lb"
check 'echo "$la" | grep -q "head=${C1:0:7} dirty=0 ver=v1"' "treeA ran at c1, clean"
check 'echo "$lb" | grep -q "head=${C2:0:7} dirty=0 ver=v2"' "treeB ran at c2, clean although treeA had modified results/tracked.json"
check 'echo "$la" | grep -q "cwd=$FSQ_HOME/wt/20260101-000300_treeA"' "treeA ran in its own worktree"
check '[ "$(git -C "$REPO" rev-parse HEAD)" = "$C1" ] && git -C "$REPO" diff --quiet HEAD' "shared checkout untouched"
check '[ -f "$FSQ_HOME/done/20260101-000300_treeA/files/results/tracked.json" ] && [ -f "$FSQ_HOME/done/20260101-000300_treeA/files/results/treeA.json" ]' "treeA's results collected into done/<id>/files"
check '[ -L "$FSQ_HOME/wt/20260101-000300_treeA/scratch/checkpoints" ]' "scratch/checkpoints is the shared checkpoint dir"
ack_all
check '[ ! -e "$FSQ_HOME/wt/20260101-000300_treeA" ] && [ "$(git -C "$REPO" worktree list | wc -l)" = 1 ]' "ack removed the worktrees"
"$FSQ" set-max 1 >/dev/null

echo "== lost: kill a running job and its wrapper with SIGKILL"
submit 20260101-000400_lostA "$C1" experiments/job.sh lostA 30 >/dev/null
submit 20260101-000401_lostB "$C1" experiments/job.sh lostB 0.2 >/dev/null
sleep 1
d="$FSQ_HOME/running/20260101-000400_lostA"
jp=$(cat "$d/job_pid"); wp=$(cat "$d/wrapper_pid")
kill -KILL "$wp"; kill -KILL -- "-$jp"; sleep 0.3
check '[ "$(n_in running)" = 1 ] && [ "$(starts_of lostB)" = 0 ]' "after the kill, lostA still shows running and lostB waits (nothing has noticed yet)"
"$FSQ" dispatch            # what the next submit or the cron line would do
wait_idle 30
check '[ "$(cat "$FSQ_HOME/done/20260101-000400_lostA/status")" = lost ]' "lostA recorded as lost"
check '[ "$(starts_of lostA)" = 1 ] && [ "$(starts_of lostB)" = 1 ]' "lostA not restarted; lostB ran"
ack_all

echo "== cancel: one running, one pending"
submit 20260101-000500_canA "$C1" experiments/job.sh canA 30 >/dev/null
submit 20260101-000501_canB "$C1" experiments/job.sh canB 30 >/dev/null
sleep 1
"$FSQ" cancel 20260101-000501_canB | sed 's/^/  /'
"$FSQ" cancel 20260101-000500_canA | sed 's/^/  /'
wait_idle 30
check '[ "$(cat "$FSQ_HOME/done/20260101-000500_canA/status")" = cancelled ] && [ "$(cat "$FSQ_HOME/done/20260101-000501_canB/status")" = cancelled ]' "both cancelled"
check '[ "$(starts_of canB)" = 0 ]' "the cancelled pending job never started"
ack_all

echo "== pause"
"$FSQ" pause >/dev/null
submit 20260101-000600_pause "$C1" experiments/job.sh pause 0.2 >/dev/null
sleep 1
check '[ "$(n_in pending)" = 1 ] && [ "$(starts_of pause)" = 0 ]' "paused: submitted job waits"
"$FSQ" resume >/dev/null
wait_idle 30
check '[ "$(starts_of pause)" = 1 ]' "resume started it"
echo "  status:"; "$FSQ" status | sed 's/^/    /'
ack_all

echo "== idle: nothing left running"
sleep 1
left=$(pgrep -af "$FSQ_HOME" | grep -v pgrep || true)
check '[ -z "$left" ]' "no fsq processes remain${left:+: $left}"

echo
echo "passed $PASS, failed $FAIL"
[ "$FAIL" = 0 ]
