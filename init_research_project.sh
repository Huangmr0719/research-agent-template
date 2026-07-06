#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$(pwd)"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"

log() {
  printf '[research-init] %s\n' "$*"
}

backup_if_exists() {
  local path="$1"
  if [[ -e "$path" ]]; then
    local backup="${path}.bak.${TIMESTAMP}"
    mv "$path" "$backup"
    log "Backed up existing ${path#$TARGET_DIR/} -> ${backup#$TARGET_DIR/}"
  fi
}

copy_file() {
  local src="$1"
  local dst="$2"
  backup_if_exists "$dst"
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  log "Created ${dst#$TARGET_DIR/}"
}

ensure_dir() {
  local dir="$1"
  mkdir -p "$dir"
  log "Ensured directory ${dir#$TARGET_DIR/}"
}

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    printf 'Missing template file: %s\n' "$path" >&2
    exit 1
  fi
}

main() {
  log "Initializing research agent workflow in $TARGET_DIR"

  require_file "$SCRIPT_DIR/tools/run_with_feishu_notify.sh"
  require_file "$SCRIPT_DIR/tools/feishu_notify.py"
  require_file "$SCRIPT_DIR/tools/summarize_experiment.py"
  require_file "$SCRIPT_DIR/tools/analyze_with_agent.py"
  require_file "$SCRIPT_DIR/templates/AGENTS.md"
  require_file "$SCRIPT_DIR/templates/README_AGENT_WORKFLOW.md"
  require_file "$SCRIPT_DIR/examples/toy_success.sh"
  require_file "$SCRIPT_DIR/examples/toy_failed.sh"

  backup_if_exists "$TARGET_DIR/tools"
  backup_if_exists "$TARGET_DIR/AGENTS.md"
  backup_if_exists "$TARGET_DIR/README_AGENT_WORKFLOW.md"

  ensure_dir "$TARGET_DIR/logs"
  ensure_dir "$TARGET_DIR/outputs"
  ensure_dir "$TARGET_DIR/experiments"
  ensure_dir "$TARGET_DIR/experiments/summaries"
  ensure_dir "$TARGET_DIR/experiments/runs"
  ensure_dir "$TARGET_DIR/examples"

  copy_file "$SCRIPT_DIR/tools/run_with_feishu_notify.sh" "$TARGET_DIR/tools/run_with_feishu_notify.sh"
  copy_file "$SCRIPT_DIR/tools/feishu_notify.py" "$TARGET_DIR/tools/feishu_notify.py"
  copy_file "$SCRIPT_DIR/tools/summarize_experiment.py" "$TARGET_DIR/tools/summarize_experiment.py"
  copy_file "$SCRIPT_DIR/tools/analyze_with_agent.py" "$TARGET_DIR/tools/analyze_with_agent.py"
  copy_file "$SCRIPT_DIR/templates/AGENTS.md" "$TARGET_DIR/AGENTS.md"
  copy_file "$SCRIPT_DIR/templates/README_AGENT_WORKFLOW.md" "$TARGET_DIR/README_AGENT_WORKFLOW.md"
  copy_file "$SCRIPT_DIR/examples/toy_success.sh" "$TARGET_DIR/examples/toy_success.sh"
  copy_file "$SCRIPT_DIR/examples/toy_failed.sh" "$TARGET_DIR/examples/toy_failed.sh"

  chmod +x "$TARGET_DIR/tools/run_with_feishu_notify.sh"
  chmod +x "$TARGET_DIR/tools/feishu_notify.py"
  chmod +x "$TARGET_DIR/tools/summarize_experiment.py"
  chmod +x "$TARGET_DIR/tools/analyze_with_agent.py"
  chmod +x "$TARGET_DIR/examples/toy_success.sh"
  chmod +x "$TARGET_DIR/examples/toy_failed.sh"

  log "Done."
  cat <<'EOF'

Toy test commands:
  ./tools/run_with_feishu_notify.sh --name toy_success --note "toy success notification check" -- bash examples/toy_success.sh
  ./tools/run_with_feishu_notify.sh --name toy_failed -- bash examples/toy_failed.sh
  ./tools/run_with_feishu_notify.sh --name toy_interrupt -- bash -c "sleep 60"

For Feishu delivery, configure an installed Feishu CLI or set FEISHU_CLI_SEND_COMMAND.
EOF
}

main "$@"
