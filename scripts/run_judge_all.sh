#!/bin/bash
# Judge every audited model in the response log, pushing each result as it lands.
#
# Same three properties as the response sweep, for the same reasons: detached so
# a dropped notebook session does not kill it, locked so a second launch refuses
# instead of putting two models on one card, and pushed per model so a container
# recycle costs at most the one in flight.
#
# KNOWN COST: the judge is loaded once PER AUDITED MODEL, not once for the sweep,
# because each model is a separate `run_judge.py` process. A 14B judge off
# network storage is about twelve minutes, so four models pay roughly forty-five
# minutes of loading for forty minutes of judging. Worth fixing by moving the
# loop inside the Python process; not fixed yet, and recorded here rather than
# discovered from a wall clock.
#
# Each model resumes from its own checkpoint, so a recycle mid-sweep costs the
# chunk in flight — not the model, and not the sweep.
#
#   HF_TOKEN=… GIT_TOKEN=… nohup bash scripts/run_judge_all.sh &
#   tail -f logs/judge.log

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DOMAIN="${1:-finance}"
LOCK="$ROOT/logs/.judge.lock"
PY="$ROOT/.venv/bin/python"
mkdir -p logs
export HF_HOME="${HF_HOME:-/home/jovyan/vault/grail-cache/hf}"

if ! mkdir "$LOCK" 2>/dev/null; then
  holder="$(cat "$LOCK/pid" 2>/dev/null || echo '')"
  if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
    echo "ALREADY RUNNING — pid $holder. Wait for logs/JUDGE_DONE."; exit 1
  fi
  echo "Stale lock from pid ${holder:-unknown} — taking it."
  rm -rf "$LOCK" && mkdir "$LOCK"
fi
echo $$ > "$LOCK/pid"; date '+%F %T' > "$LOCK/started"
trap 'rm -rf "$LOCK"' EXIT INT TERM
rm -f logs/JUDGE_DONE

[ -x "$PY" ] || { echo "No venv at $PY — run scripts/bootstrap_server.py"; exit 1; }

MODELS=$("$PY" - <<'EOF'
import os, sys
sys.path.insert(0, os.getcwd())
from config import RUN_DIR
from grail.run.pilot import models_in
from grail.run.store import load
print("\n".join(models_in(load(os.path.join(RUN_DIR, "finance", "responses.jsonl")))))
EOF
)

ok=0; failed=0
while read -r model; do
  [ -z "$model" ] && continue
  echo ""; echo "===================================================================="
  echo "JUDGING  $(date '+%H:%M:%S')  $model"
  echo "===================================================================="

  # A finished verdict file is not re-judged. Rerunning the sweep after one
  # model failed should cost that model, not all four.
  if [ -f "data/processed/runs/$DOMAIN/judge_${model//\//_}.json" ] && [ "${FORCE:-}" != "1" ]; then
    echo "  already judged — skipping (FORCE=1 to redo)"; ok=$((ok+1)); continue
  fi

  if "$PY" scripts/run_judge.py "$DOMAIN" --model "$model" --local --eager; then
    ok=$((ok+1))
    git add -A
    git -c user.email=grail@local -c user.name=grail \
        commit -q -m "Judge verdicts: $model" || echo "  (nothing new)"
    if [ -n "${GIT_TOKEN:-}" ]; then
      git push -q "https://prasadwatane:${GIT_TOKEN}@github.com/prasadwatane/CASE-STUDY.git" main \
        && echo "PUSHED $model" || echo "PUSH FAILED $model — committed locally only"
    else
      echo "NOT PUSHED $model — GIT_TOKEN unset; a recycle would lose this"
    fi
  else
    failed=$((failed+1)); echo "FAILED $model — continuing"
  fi
done <<< "$MODELS"

echo ""; echo "JUDGE SWEEP COMPLETE $(date '+%H:%M:%S') — $ok ok, $failed failed"
echo "$ok ok, $failed failed at $(date '+%F %T')" > logs/JUDGE_DONE
