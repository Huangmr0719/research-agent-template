#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$(pwd)"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"

TEST_FEISHU=0
UPDATE_TOOLS=0

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

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --test-feishu)
        TEST_FEISHU=1
        shift
        ;;
      --update-tools)
        UPDATE_TOOLS=1
        shift
        ;;
      -h|--help)
        cat <<'EOF'
Usage:
  bash init_research_project.sh [--test-feishu] [--update-tools]

Options:
  --test-feishu   Run Feishu smoke test after initialization
  --update-tools  Update generic tools only; do not touch project adapters or outputs
EOF
        exit 0
        ;;
      *)
        printf 'Unknown argument: %s\n' "$1" >&2
        exit 1
        ;;
    esac
  done
}

copy_generic_tools() {
  copy_file "$SCRIPT_DIR/tools/run_with_feishu_notify.sh" "$TARGET_DIR/tools/run_with_feishu_notify.sh"
  copy_file "$SCRIPT_DIR/tools/feishu_notify.py" "$TARGET_DIR/tools/feishu_notify.py"
  copy_file "$SCRIPT_DIR/tools/summarize_experiment.py" "$TARGET_DIR/tools/summarize_experiment.py"
  copy_file "$SCRIPT_DIR/tools/analyze_with_agent.py" "$TARGET_DIR/tools/analyze_with_agent.py"
  copy_file "$SCRIPT_DIR/tools/compare_experiments.py" "$TARGET_DIR/tools/compare_experiments.py"
  copy_file "$SCRIPT_DIR/tools/test_feishu_notify.sh" "$TARGET_DIR/tools/test_feishu_notify.sh"
  copy_file "$SCRIPT_DIR/tools/init_paper_context.sh" "$TARGET_DIR/tools/init_paper_context.sh"

  chmod +x "$TARGET_DIR/tools/run_with_feishu_notify.sh"
  chmod +x "$TARGET_DIR/tools/feishu_notify.py"
  chmod +x "$TARGET_DIR/tools/summarize_experiment.py"
  chmod +x "$TARGET_DIR/tools/analyze_with_agent.py"
  chmod +x "$TARGET_DIR/tools/compare_experiments.py"
  chmod +x "$TARGET_DIR/tools/test_feishu_notify.sh"
  chmod +x "$TARGET_DIR/tools/init_paper_context.sh"
}

main() {
  parse_args "$@"

  log "Initializing Research-Code-Agent workflow in $TARGET_DIR"

  require_file "$SCRIPT_DIR/tools/run_with_feishu_notify.sh"
  require_file "$SCRIPT_DIR/tools/feishu_notify.py"
  require_file "$SCRIPT_DIR/tools/summarize_experiment.py"
  require_file "$SCRIPT_DIR/tools/analyze_with_agent.py"
  require_file "$SCRIPT_DIR/tools/compare_experiments.py"
  require_file "$SCRIPT_DIR/tools/project_results_adapter.py"
  require_file "$SCRIPT_DIR/tools/test_feishu_notify.sh"
  require_file "$SCRIPT_DIR/tools/init_paper_context.sh"
  require_file "$SCRIPT_DIR/templates/AGENTS.md"
  require_file "$SCRIPT_DIR/templates/README_AGENT_WORKFLOW.md"
  require_file "$SCRIPT_DIR/templates/PAPER_CONTEXT_TEMPLATE.md"
  require_file "$SCRIPT_DIR/examples/toy_success.sh"
  require_file "$SCRIPT_DIR/examples/toy_failed.sh"

  if [[ "$UPDATE_TOOLS" -eq 1 ]]; then
    log "Updating generic tools only."
    copy_generic_tools
    log "Skipped tools/project_results_adapter.py, PAPER_CONTEXT.md, papers/, logs/, outputs/, experiments/, and project code."
    log "Done."
    exit 0
  fi

  backup_if_exists "$TARGET_DIR/tools"
  backup_if_exists "$TARGET_DIR/AGENTS.md"
  backup_if_exists "$TARGET_DIR/README_AGENT_WORKFLOW.md"

  ensure_dir "$TARGET_DIR/papers"
  ensure_dir "$TARGET_DIR/logs"
  ensure_dir "$TARGET_DIR/outputs"
  ensure_dir "$TARGET_DIR/experiments"
  ensure_dir "$TARGET_DIR/experiments/summaries"
  ensure_dir "$TARGET_DIR/experiments/runs"
  ensure_dir "$TARGET_DIR/examples"

  copy_generic_tools
  if [[ -f "$TARGET_DIR/tools/project_results_adapter.py" ]]; then
    log "Skipped tools/project_results_adapter.py (already exists, not overwriting project-specific adapter)"
  else
    copy_file "$SCRIPT_DIR/tools/project_results_adapter.py" "$TARGET_DIR/tools/project_results_adapter.py"
  fi
  copy_file "$SCRIPT_DIR/templates/AGENTS.md" "$TARGET_DIR/AGENTS.md"
  copy_file "$SCRIPT_DIR/templates/README_AGENT_WORKFLOW.md" "$TARGET_DIR/README_AGENT_WORKFLOW.md"
  copy_file "$SCRIPT_DIR/templates/PAPER_CONTEXT_TEMPLATE.md" "$TARGET_DIR/templates/PAPER_CONTEXT_TEMPLATE.md"
  copy_file "$SCRIPT_DIR/examples/toy_success.sh" "$TARGET_DIR/examples/toy_success.sh"
  copy_file "$SCRIPT_DIR/examples/toy_failed.sh" "$TARGET_DIR/examples/toy_failed.sh"

  chmod +x "$TARGET_DIR/tools/project_results_adapter.py"
  chmod +x "$TARGET_DIR/examples/toy_success.sh"
  chmod +x "$TARGET_DIR/examples/toy_failed.sh"

  log "Done."

  if [[ "$TEST_FEISHU" -eq 1 ]]; then
    log "Running Feishu smoke test..."
    "$TARGET_DIR/tools/test_feishu_notify.sh" || true
  else
    cat <<'EOF'

Next step: run ./tools/test_feishu_notify.sh to verify Feishu notification.

Optional paper context:
  1. Put the paper at papers/paper.pdf
  2. Run ./tools/init_paper_context.sh
  3. Ask your Agent to fill PAPER_CONTEXT.md based on the paper, README, and code.

Toy test commands:
  ./tools/run_with_feishu_notify.sh --name toy_success --note "toy success notification check" -- bash examples/toy_success.sh
  ./tools/run_with_feishu_notify.sh --name toy_failed -- bash examples/toy_failed.sh
  ./tools/run_with_feishu_notify.sh --name toy_interrupt -- bash -c "sleep 60"

For Feishu delivery, configure an installed Feishu CLI or set FEISHU_CLI_SEND_COMMAND.
EOF
  fi
}

main "$@"
