#!/usr/bin/env bash
# CAO statusline.
# Reports tmux session presence and a worker count (claude / codex / unknown).

set -euo pipefail

detect_session() {
  if [[ -n "${CAO_SESSION:-}" ]]; then
    printf '%s\n' "$CAO_SESSION"
    return
  fi
  if [[ -n "${TMUX:-}" ]]; then
    local current
    current="$(tmux display-message -p '#{session_name}' 2>/dev/null || true)"
    if [[ -n "$current" ]]; then
      printf '%s\n' "$current"
      return
    fi
  fi
  if tmux has-session -t CAO 2>/dev/null; then
    printf 'CAO\n'
  else
    printf 'CAO\n'
  fi
}

session="$(detect_session)"
project_dir="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
state_dir="${CAO_STATE_DIR:-$project_dir/.cao}"
targets_file="${CAO_TARGETS_FILE:-$state_dir/targets.tsv}"

if ! tmux has-session -t "$session" 2>/dev/null; then
  printf 'cao: %s (no session)' "$session"
  exit 0
fi

manager="$(tmux show-options -qv -t "$session" @cao_manager_window 2>/dev/null || true)"
windows="$(tmux list-windows -t "$session" -F '#{window_id}|#{window_name}|#{@cao_runner}' 2>/dev/null || true)"

total=0
claude=0
codex=0
other=0
while IFS='|' read -r win_id _name runner; do
  [[ -z "$win_id" ]] && continue
  [[ -n "$manager" && "$win_id" == "$manager" ]] && continue
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
