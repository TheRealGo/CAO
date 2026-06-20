#!/usr/bin/env bash
# CAO statusline.
# Reports tmux session presence and a worker count (claude / codex / unknown).

set -euo pipefail

session="${CAO_SESSION:-cao}"
project_dir="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
state_dir="${CAO_STATE_DIR:-$project_dir/.cao}"
targets_file="${CAO_TARGETS_FILE:-$state_dir/targets.tsv}"

if ! tmux has-session -t "$session" 2>/dev/null; then
  printf 'cao: %s (no session)' "$session"
  exit 0
fi

windows="$(tmux list-windows -t "$session" -F '#{window_name}|#{@cao_runner}' 2>/dev/null || true)"

total=0
claude=0
codex=0
other=0
while IFS='|' read -r name runner; do
  [[ -z "$name" ]] && continue
  [[ "$name" == "pm" ]] && continue
  total=$((total + 1))
  case "$runner" in
    claude) claude=$((claude + 1)) ;;
    codex)  codex=$((codex + 1)) ;;
    *)      other=$((other + 1)) ;;
  esac
done <<< "$windows"

if [[ -f "$targets_file" ]]; then
  while IFS=$'\t' read -r target runner _name; do
    [[ -z "$target" ]] && continue
    if ! tmux display-message -p -t "$target" '#{window_id}' >/dev/null 2>&1; then
      continue
    fi
    if [[ "$(tmux display-message -p -t "$target" '#{session_name}' 2>/dev/null || true)" == "$session" ]]; then
      continue
    fi
    total=$((total + 1))
    case "$runner" in
      claude) claude=$((claude + 1)) ;;
      codex)  codex=$((codex + 1)) ;;
      *)      other=$((other + 1)) ;;
    esac
  done < "$targets_file"
fi

if [[ "$total" -eq 0 ]]; then
  printf 'cao: %s | 0 workers' "$session"
else
  if [[ "$other" -gt 0 ]]; then
    printf 'cao: %s | %d workers (claude:%d codex:%d ?:%d)' "$session" "$total" "$claude" "$codex" "$other"
  else
    printf 'cao: %s | %d workers (claude:%d codex:%d)' "$session" "$total" "$claude" "$codex"
  fi
fi
