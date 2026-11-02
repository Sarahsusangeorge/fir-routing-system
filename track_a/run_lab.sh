#!/usr/bin/env bash
# One command to START or RESUME the full experiment. Safe against closed terminals, crashes,
# idle-sleep and (because finished runs are checkpointed) even a logout or reboot.
#
#   bash run_lab.sh            start / resume in the background (tmux session "fir")
#   bash run_lab.sh --status   show progress without touching the run
#
# If the run is ever killed, just log back in and run:  bash run_lab.sh
# It skips every run that already finished (see the ./checkpoints folder) and carries on.

set -u
cd "$(dirname "$(readlink -f "$0")")"

SESSION=fir
MAX_TRIES=6
RETRY_WAIT=${RETRY_WAIT:-30}

is_running() {
  # matches only the real interpreter process, not editors/tail/grep that merely mention the file name
  pgrep -f '^[^ ]*python[0-9.]* -u fir_pipeline_lab\.py' >/dev/null 2>&1
}

progress() {
  echo "== finished runs per model (from ./checkpoints) =="
  python3 - <<'PY'
import glob, json, os
files = sorted(glob.glob("checkpoints/*.json"))
if not files:
    print("  none yet")
for f in files:
    try:
        n = len(json.load(open(f)))
    except Exception:
        n = "unreadable"
    print(f"  {os.path.basename(f)[:-5]:<26} {n} runs done")
PY
  echo "== last log lines =="
  tail -n 8 run_log.txt 2>/dev/null || echo "  no log yet"
  if is_running; then
    echo "== STATUS: RUNNING =="
  else
    echo "== STATUS: NOT RUNNING (finished, or it was stopped; run 'bash run_lab.sh' to resume) =="
  fi
}

inner() {
  # shellcheck disable=SC1091
  source fir_env/bin/activate || { echo "fir_env missing: run 'bash setup_lab.sh' first" | tee -a run_log.txt; return 1; }
  export MPLBACKEND=Agg

  echo "[$(date '+%F %T')] converting notebook to script" >> run_log.txt
  jupyter nbconvert --to script fir_pipeline_lab.ipynb >> run_log.txt 2>&1 \
    || { echo "[$(date '+%F %T')] nbconvert failed" >> run_log.txt; return 1; }

  # keep the machine from idle-sleeping while we run, if the system allows it
  INHIBIT=()
  if command -v systemd-inhibit >/dev/null 2>&1 && systemd-inhibit --what=idle:sleep --why="check" true >/dev/null 2>&1; then
    INHIBIT=(systemd-inhibit --what=idle:sleep --who="FIR experiment" --why="long training run")
  fi

  for try in $(seq 1 "$MAX_TRIES"); do
    echo "[$(date '+%F %T')] attempt $try/$MAX_TRIES (already-finished runs are skipped)" >> run_log.txt
    ${INHIBIT[@]+"${INHIBIT[@]}"} python -u fir_pipeline_lab.py >> run_log.txt 2>&1
    rc=$?
    if [ "$rc" -eq 0 ]; then
      echo "[$(date '+%F %T')] FINISHED OK" >> run_log.txt
      return 0
    fi
    echo "[$(date '+%F %T')] exited with code $rc; retrying in ${RETRY_WAIT}s" >> run_log.txt
    sleep "$RETRY_WAIT"
  done
  echo "[$(date '+%F %T')] gave up after $MAX_TRIES attempts; read the errors above" >> run_log.txt
  return 1
}

launch() {
  if [ ! -d fir_env ]; then
    echo "fir_env not found. Run 'bash setup_lab.sh' first."; exit 1
  fi
  if is_running; then
    echo "A run is already going. Check it with:  bash run_lab.sh --status"; exit 0
  fi
  if command -v tmux >/dev/null 2>&1; then
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    tmux new-session -d -s "$SESSION" "bash '$PWD/run_lab.sh' --inner"
    echo "Started in tmux session '$SESSION'."
    echo "  watch it live:   tmux attach -t $SESSION      (leave it running: press Ctrl+B, then D)"
  else
    nohup bash "$PWD/run_lab.sh" --inner >/dev/null 2>&1 &
    echo "tmux not installed, started with nohup instead."
    echo "  watch it live:   tail -f run_log.txt"
  fi
  echo "  progress check:  bash run_lab.sh --status"
}

case "${1:-}" in
  --inner)  inner; exit $? ;;
  --status) source fir_env/bin/activate 2>/dev/null; progress ;;
  *)        launch ;;
esac
