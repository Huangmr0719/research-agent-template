#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_PATH="$PROJECT_DIR/templates/PAPER_CONTEXT_TEMPLATE.md"
CONTEXT_PATH="$PROJECT_DIR/PAPER_CONTEXT.md"
PAPER_PATH="$PROJECT_DIR/papers/paper.pdf"

log() {
  printf '[paper-context] %s\n' "$*"
}

if [[ ! -f "$TEMPLATE_PATH" ]]; then
  printf '[paper-context] ERROR: Missing template: %s\n' "$TEMPLATE_PATH" >&2
  exit 1
fi

mkdir -p "$PROJECT_DIR/papers"

if [[ ! -f "$PAPER_PATH" ]]; then
  shopt -s nullglob
  pdfs=("$PROJECT_DIR"/papers/*.pdf)
  shopt -u nullglob
  if [[ "${#pdfs[@]}" -eq 1 ]]; then
    log "Found paper PDF: papers/$(basename "${pdfs[0]}")"
  elif [[ "${#pdfs[@]}" -gt 1 ]]; then
    cat <<EOF
Multiple PDF files found under papers/.
Use the intended paper as:
papers/paper.pdf
EOF
  else
    cat <<EOF
Please place the paper PDF at:
papers/paper.pdf
EOF
  fi
fi

if [[ -f "$CONTEXT_PATH" ]]; then
  log "PAPER_CONTEXT.md already exists; not overwriting."
else
  cp "$TEMPLATE_PATH" "$CONTEXT_PATH"
  log "Created PAPER_CONTEXT.md from template."
fi
