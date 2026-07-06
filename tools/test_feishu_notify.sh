#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

log() {
  printf '[test-feishu] %s\n' "$*"
}

error() {
  printf '[test-feishu] ERROR: %s\n' "$*" >&2
}

SMOKE_NAME="feishu_smoke_test"
SMOKE_NOTE="Research-Code-Agent 初始化后飞书通知测试。如果收到这条消息，说明当前项目的飞书通知链路可用。"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
HOST_NAME="$(hostname 2>/dev/null || printf 'unknown')"
GIT_COMMIT="$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || printf 'unknown')"
START_TIME="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
NOTIFY_MODE="${FEISHU_NOTIFY_MODE:-card}"

log "Running Feishu smoke test..."
log "Project: $PROJECT_DIR"
log "Host: $HOST_NAME"
log "Git commit: $GIT_COMMIT"
log "Notify mode: $NOTIFY_MODE"

SUMMARY_DIR="$PROJECT_DIR/experiments/summaries"
RUN_DIR="$PROJECT_DIR/experiments/runs"
mkdir -p "$SUMMARY_DIR" "$RUN_DIR"

STATUS_JSON="$RUN_DIR/${SMOKE_NAME}_${TIMESTAMP}.status.json"
python3 - "$STATUS_JSON" "$SMOKE_NAME" "$HOST_NAME" "$GIT_COMMIT" "$START_TIME" "$SMOKE_NOTE" <<'PY'
import json
import sys

path = sys.argv[1]
data = {
    "experiment_name": sys.argv[2],
    "note": sys.argv[6],
    "status": "success",
    "exit_code": 0,
    "signal": "unknown",
    "host": sys.argv[3],
    "git_commit": sys.argv[4],
    "command": "bash tools/test_feishu_notify.sh",
    "start_time": sys.argv[5],
    "end_time": sys.argv[5],
    "duration_seconds": 0,
    "log_path": "N/A",
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
PY

SUMMARY_JSON="$SUMMARY_DIR/${SMOKE_NAME}.summary.json"
python3 - "$SUMMARY_JSON" "$SMOKE_NAME" "$HOST_NAME" "$GIT_COMMIT" "$START_TIME" "$SMOKE_NOTE" <<'PY'
import json
import sys

path = sys.argv[1]
summary = {
    "experiment_name": sys.argv[2],
    "note": sys.argv[6],
    "status": "success",
    "facts": {
        "exit_code": 0,
        "signal": "unknown",
        "command": "bash tools/test_feishu_notify.sh",
        "host": sys.argv[3],
        "git_commit": sys.argv[4],
        "start_time": sys.argv[5],
        "end_time": sys.argv[5],
        "duration_seconds": 0,
        "duration": "0s",
        "log_path": "N/A",
    },
    "metrics": {},
    "metrics_source": "none",
    "adapter_status": "not_applicable",
    "log_tail": ["Smoke test - no real log output."],
    "traceback": [],
    "analysis": {
        "concise_summary": "飞书通知 smoke test，验证通知链路可用性。",
        "evidence": [],
        "possible_causes": [],
        "next_steps": [],
        "confidence": "high",
    },
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)
    f.write("\n")
PY

log "Created temporary summary: $SUMMARY_JSON"

if python3 "$SCRIPT_DIR/feishu_notify.py" \
  --status success \
  --name "$SMOKE_NAME" \
  --metadata "$STATUS_JSON" \
  --summary "$SUMMARY_JSON"; then
  log "Feishu smoke test passed. Check your Feishu client for the test message."
  exit 0
else
  error "Feishu smoke test failed."
  error "Please check:"
  error "  1. FEISHU_* environment variables are set correctly"
  error "  2. Feishu CLI is installed and logged in"
  error "  3. Webhook URL or CLI command is valid"
  error "  4. Network access to Feishu API is available"
  exit 1
fi
