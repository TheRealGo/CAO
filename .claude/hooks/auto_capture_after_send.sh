#!/usr/bin/env bash
# PostToolUse hook for CAO.
# When the previous Bash tool call ran `tmux send-keys ... -t <target>`,
# briefly capture the target pane so the supervisor can see what landed.
#
# Input  (stdin): JSON describing the tool call.
# Output (stdout): an extra context block to inject into the conversation.

set -euo pipefail

input="$(cat)"

if command -v jq >/dev/null 2>&1; then
  tool_name="$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null || true)"
  command_str="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
else
  tool_name="$(printf '%s' "$input" | grep -oE '"tool_name"[[:space:]]*:[[:space:]]*"[^"]+"' | head -1 | sed -E 's/.*"([^"]+)"[[:space:]]*$/\1/')"
  command_str="$(printf '%s' "$input" | grep -oE '"command"[[:space:]]*:[[:space:]]*"[^"]+"' | head -1 | sed -E 's/.*"([^"]+)"[[:space:]]*$/\1/')"
fi

[[ "$tool_name" == "Bash" ]] || exit 0
[[ "$command_str" == *"tmux send-keys"* ]] || exit 0

target="$(printf '%s' "$command_str" | grep -oE '\-t[[:space:]]+[^ ;|&"]+' | head -1 | sed -E 's/^-t[[:space:]]+//')"
[[ -n "$target" ]] || exit 0

capture="$(tmux capture-pane -t "$target" -p -S -40 2>/dev/null || true)"
[[ -n "$capture" ]] || exit 0

printf '\n[CAO auto-capture of %s after tmux send-keys (last 40 lines):]\n%s\n' "$target" "$capture"
