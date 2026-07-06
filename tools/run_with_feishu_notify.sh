#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./tools/run_with_feishu_notify.sh --name EXPERIMENT_NAME [--note NOTE] -- COMMAND [ARGS...]

Example:
  ./tools/run_with_feishu_notify.sh --name exp_042 --note "Remove region mask module" -- python train.py --config configs/exp_042.yaml
EOF
}

if [[ $# -lt 3 ]]; then
  usage >&2
  exit 2
fi

EXPERIMENT_NAME=""
EXPERIMENT_NOTE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      if [[ $# -lt 2 ]]; then
        printf 'Missing value for --name\n' >&2
        exit 2
      fi
      EXPERIMENT_NAME="$2"
      shift 2
      ;;
    --note)
      if [[ $# -lt 2 ]]; then
        printf 'Missing value for --note\n' >&2
        exit 2
      fi
      EXPERIMENT_NOTE="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$EXPERIMENT_NAME" || $# -eq 0 ]]; then
  usage >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
LOG_DIR="$PROJECT_DIR/logs"
SUMMARY_DIR="$PROJECT_DIR/experiments/summaries"
RUN_DIR="$PROJECT_DIR/experiments/runs"
LOG_PATH="$LOG_DIR/${EXPERIMENT_NAME}_${TIMESTAMP}.log"
STATUS_PATH="$RUN_DIR/${EXPERIMENT_NAME}_${TIMESTAMP}.status.json"
TAIL_PATH="$RUN_DIR/${EXPERIMENT_NAME}_${TIMESTAMP}.tail.txt"
COMMAND_DISPLAY="$(printf '%q ' "$@")"
HOST_NAME="$(hostname 2>/dev/null || printf 'unknown')"
GIT_COMMIT="$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || printf 'unknown')"
START_EPOCH="$(date +%s)"
START_TIME="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

mkdir -p "$LOG_DIR" "$SUMMARY_DIR" "$RUN_DIR"

write_status_json() {
  local status="$1"
  local exit_code="$2"
  local end_epoch="$3"
  local end_time="$4"
  local signal="${5:-unknown}"
  local duration_seconds="$((end_epoch - START_EPOCH))"

  EXPERIMENT_NAME_JSON="$EXPERIMENT_NAME" \
  STATUS_JSON="$status" \
  EXIT_CODE_JSON="$exit_code" \
  SIGNAL_JSON="$signal" \
  NOTE_JSON="$EXPERIMENT_NOTE" \
  HOST_NAME_JSON="$HOST_NAME" \
  GIT_COMMIT_JSON="$GIT_COMMIT" \
  COMMAND_DISPLAY_JSON="$COMMAND_DISPLAY" \
  START_TIME_JSON="$START_TIME" \
  END_TIME_JSON="$end_time" \
  DURATION_SECONDS_JSON="$duration_seconds" \
  LOG_PATH_JSON="$LOG_PATH" \
  python3 - "$STATUS_PATH" <<'PY'
import json
import os
import sys

path = sys.argv[1]
data = {
    "experiment_name": os.environ["EXPERIMENT_NAME_JSON"],
    "note": os.environ.get("NOTE_JSON", ""),
    "status": os.environ["STATUS_JSON"],
    "exit_code": int(os.environ["EXIT_CODE_JSON"]),
    "signal": os.environ["SIGNAL_JSON"],
    "host": os.environ["HOST_NAME_JSON"],
    "git_commit": os.environ["GIT_COMMIT_JSON"],
    "command": os.environ["COMMAND_DISPLAY_JSON"].strip(),
    "start_time": os.environ["START_TIME_JSON"],
    "end_time": os.environ["END_TIME_JSON"],
    "duration_seconds": int(os.environ["DURATION_SECONDS_JSON"]),
    "log_path": os.environ["LOG_PATH_JSON"],
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
PY
}

summarize() {
  local status="$1"
  local result_json="$STATUS_PATH"
  local metrics_json="${METRICS_JSON:-}"

  local args=(
    "$SCRIPT_DIR/summarize_experiment.py"
    --name "$EXPERIMENT_NAME"
    --status "$status"
    --note "$EXPERIMENT_NOTE"
    --log "$LOG_PATH"
    --result-json "$result_json"
    --output-dir "$SUMMARY_DIR"
  )

  if [[ -n "$metrics_json" && -f "$metrics_json" ]]; then
    args+=(--metrics-json "$metrics_json")
  elif [[ -f "$PROJECT_DIR/metrics.json" ]]; then
    args+=(--metrics-json "$PROJECT_DIR/metrics.json")
  elif [[ -f "$PROJECT_DIR/result.json" ]]; then
    args+=(--metrics-json "$PROJECT_DIR/result.json")
  fi

  python3 "${args[@]}" || true
}

analyze() {
  local summary_json="$SUMMARY_DIR/${EXPERIMENT_NAME}.summary.json"
  if [[ -f "$summary_json" ]]; then
    python3 "$SCRIPT_DIR/analyze_with_agent.py" --summary "$summary_json" || true
  fi
}

notify() {
  local status="$1"
  local summary_json="$SUMMARY_DIR/${EXPERIMENT_NAME}.summary.json"

  if [[ "$status" == "failed" || "$status" == "interrupted" ]]; then
    tail -n 80 "$LOG_PATH" > "$TAIL_PATH" 2>/dev/null || true
    python3 "$SCRIPT_DIR/feishu_notify.py" \
      --status "$status" \
      --name "$EXPERIMENT_NAME" \
      --metadata "$STATUS_PATH" \
      --summary "$summary_json" \
      --tail-log "$TAIL_PATH" || true
  else
    python3 "$SCRIPT_DIR/feishu_notify.py" \
      --status "$status" \
      --name "$EXPERIMENT_NAME" \
      --metadata "$STATUS_PATH" \
      --summary "$summary_json" || true
  fi
}

finish() {
  local status="$1"
  local exit_code="$2"
  local signal="${3:-unknown}"
  local end_epoch
  local end_time
  end_epoch="$(date +%s)"
  end_time="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  write_status_json "$status" "$exit_code" "$end_epoch" "$end_time" "$signal"
  summarize "$status"
  analyze
  notify "$status"
}

interrupted() {
  local signal="$1"
  trap - INT TERM
  printf '\nInterrupted by %s\n' "$signal" >> "$LOG_PATH" 2>/dev/null || true
  finish "interrupted" 130 "$signal"
  exit 130
}

trap 'interrupted SIGINT' INT
trap 'interrupted SIGTERM' TERM

{
  printf 'Experiment: %s\n' "$EXPERIMENT_NAME"
  if [[ -n "$EXPERIMENT_NOTE" ]]; then
    printf 'Note: %s\n' "$EXPERIMENT_NOTE"
  fi
  printf 'Command: %s\n' "$COMMAND_DISPLAY"
  printf 'Host: %s\n' "$HOST_NAME"
  printf 'Git commit: %s\n' "$GIT_COMMIT"
  printf 'Start time: %s\n' "$START_TIME"
  printf 'Log path: %s\n' "$LOG_PATH"
  printf '%s\n' '--- command output ---'
} | tee "$LOG_PATH"

set +e
"$@" 2>&1 | tee -a "$LOG_PATH"
cmd_status=${PIPESTATUS[0]}
set -e

if [[ "$cmd_status" -eq 0 ]]; then
  finish "success" "$cmd_status"
else
  finish "failed" "$cmd_status"
fi

exit "$cmd_status"
