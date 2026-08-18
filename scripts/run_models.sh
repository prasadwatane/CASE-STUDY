#!/bin/bash
# Put every model in data/audit_models.txt through the frozen probe set, and
# push each one's responses the moment they exist.
#
# Three properties, each earned the hard way on the college GPU server:
#
#   DETACHED   The notebook session drops during long runs. Launched with
#              nohup + setsid this survives the kernel, so a 90-minute sweep
#              does not depend on a browser tab staying open.
#
#   LOCKED     Relaunching while a run is in flight puts two vLLM processes on
#              one card; the first claims 42 of 48 GB and both die. A lock
#              directory (mkdir is atomic, unlike test -f then touch) makes the
#              second launch refuse instead of competing.
#
#   PUSHED     Containers are recycled without warning and responses are the
#              one artefact that cannot be regenerated — a probe comes back
#              from a seed, a response is a purchase. Each model is committed
#              and pushed as it completes, so a recycle costs at most the model
#              currently running rather than the whole sweep.
#
# Environment:
#   GIT_TOKEN  required to push. Read from the environment only — never written
#              to .git/config, so it does not survive on disk.
#   HF_TOKEN   required for gated repos (Meta, Google). Ungated models run fine
#              without it; gated ones fail fast and the sweep continues.
#
# Usage:
#   HF_TOKEN=... GIT_TOKEN=... nohup bash scripts/run_models.sh &
#   tail -f logs/runs.log

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DOMAIN="${1:-finance}"
MODELS="${MODELS_FILE:-data/audit_models.txt}"
LOCK="$ROOT/logs/.run.lock"
PY="$ROOT/.venv/bin/python"

mkdir -p logs
export HF_HOME="${HF_HOME:-$ROOT/.grail-cache/hf}"

# --- lock ------------------------------------------------------------------
# mkdir succeeds or fails atomically, which test-then-create does not.
#
# A lock with no staleness check is worse than no lock: kill -9 skips the trap,
# the directory survives, and every later sweep refuses forever with no clue
# why. So a held lock is only honoured while the process that took it is still
# alive. That check is also what makes the lock safe across a container
# recycle, where no PID from the previous life exists.
if ! mkdir "$LOCK" 2>/dev/null; then
  holder="$(cat "$LOCK/pid" 2>/dev/null || echo '')"
  if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
    echo "ALREADY RUNNING — pid $holder holds $LOCK (started $(cat "$LOCK/started" 2>/dev/null))."
    echo "Wait for logs/DONE, or stop it with: pkill -f run_models.sh"
    exit 1
  fi
  echo "Stale lock from pid ${holder:-unknown} (no longer running) — taking it."
  rm -rf "$LOCK" && mkdir "$LOCK" || { echo "Cannot clear $LOCK"; exit 1; }
fi
date '+%Y-%m-%d %H:%M:%S' > "$LOCK/started"
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT INT TERM

rm -f logs/DONE

# --- wait for the card ------------------------------------------------------
# vLLM does not release GPU memory the instant its process is signalled, and a
# sweep that starts while the previous one is still letting go will OOM on its
# first model for no reason. Poll briefly rather than making the operator time
# it by hand; give up after two minutes and try anyway, because a card held by
# somebody else's job is not something waiting will fix.
if command -v nvidia-smi >/dev/null 2>&1; then
  for _ in $(seq 24); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
    [ "${used:-0}" -lt 2000 ] && break
    echo "waiting for GPU to free — ${used} MiB still held"
    sleep 5
  done
fi

[ -x "$PY" ] || { echo "No virtualenv at $PY — run scripts/bootstrap_server.py first."; exit 1; }

# --- sweep -----------------------------------------------------------------
ok=0; failed=0
while read -r repo mem; do
  case "$repo" in ''|\#*) continue ;; esac
  mem="${mem:-0.85}"

  echo ""
  echo "======================================================================"
  echo "START  $(date '+%H:%M:%S')  $repo   (gpu_mem $mem)"
  echo "======================================================================"

  if "$PY" scripts/run_probes.py "$DOMAIN" --local "$repo" --eager --gpu-mem "$mem"; then
    ok=$((ok+1))
    git add -A
    git -c user.email=grail@local -c user.name=grail \
        commit -q -m "Responses: $repo on $DOMAIN" || echo "  (nothing new to commit)"
    if [ -n "${GIT_TOKEN:-}" ]; then
      if git push -q "https://prasadwatane:${GIT_TOKEN}@github.com/prasadwatane/CASE-STUDY.git" main; then
        echo "PUSHED $repo"
      else
        echo "PUSH FAILED $repo — responses are committed locally but NOT backed up"
      fi
    else
      echo "NOT PUSHED $repo — GIT_TOKEN unset; a recycle would lose this"
    fi
  else
    failed=$((failed+1))
    echo "FAILED $repo — continuing to the next model"
  fi
done < "$MODELS"

echo ""
echo "SWEEP COMPLETE $(date '+%H:%M:%S')  —  $ok succeeded, $failed failed"
echo "$ok succeeded, $failed failed at $(date '+%Y-%m-%d %H:%M:%S')" > logs/DONE
