#!/usr/bin/env zsh
# UserPromptSubmit hook for Codex CAO.
# Reinforces recipient classification in the CAO supervisor context immediately
# after the user submits a prompt. This does not send anything to workers.

set -euo pipefail

cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "【CAO宛先判定義務】ユーザー入力を受けた直後、Workerへ何か送る前に必ず宛先を分類すること。Worker名で明示された内容だけWorker向け候補とし、宛先なしの会話、注意、確認、判断依頼、状態確認、CAO運用、hook、memory、AGENTS/CLAUDE、コンテキスト管理はCAO向けとして扱い、Workerへ送らない。Workerへ送る必要がある場合も、ユーザーの生文やCAOメタ文を転送せず、実行すべき作業指示だけに翻訳して送る。迷ったらWorkerへ送らず、まずCAOで画面確認・判断・必要ならユーザー確認を行う。"
  }
}
JSON
