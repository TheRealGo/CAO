# CAO

[English](README.md) | **日本語**

CAO(Chief Agent Officer)は、tmux 経由で他のエージェントセッションを監督する **コックピット** です。supervisor 側にも worker 側にも、**Claude Code** と **Codex CLI** の両方を使えます。

## クイックスタート

このディレクトリで Claude Code か Codex CLI のどちらかを起動してください。起動した方が supervisor になり、worker windows のデフォルトも同じ runner になります。個別の worker は `--runner` でもう一方に切り替え可能。

```sh
cd ~/CAO
claude        # supervisor = Claude Code
# または
codex         # supervisor = Codex CLI
```

そして CAO supervisor に自然言語で頼みます:

- `XXX で YYY を実装して`
- `XXX で動いている セッションを監視して`
- `追加で AAA で動いている セッションも監視して`
- `今監視している Agent たちの状況を見て、必要なら返事して`

supervisor は内部で `./bin/cao` を使って tmux ウィンドウを作成・観察・操作します。あなたが直接 `bin/cao` を叩く必要はありません。

## メンタルモデル

```text
ユーザー
 │
CAO supervisor(Claude Code または Codex CLI、このディレクトリ)
 │
tmux session: cao
 ├── window: pm
 ├── window: project-a-agent   (runner=claude)
 ├── window: project-b-agent   (runner=codex)
 └── window: project-c-agent   (runner=claude)
```

tmux スクリーンが真実の源泉(source of truth)です。CAO は `capture-pane` で見えるエージェント出力を直接観察し、応答・軌道修正・あなたへの確認を行います。

## CAO が内部でやること

`XXX で YYY を実装して` と言われたら、CAO は:

1. `cao` tmux session を作成または再利用、
2. `XXX` 用のウィンドウを作成、
3. そのディレクトリで worker runner を起動、
4. 実装リクエストを送信、
5. 定期的に画面を観察して作業を前に進めます。

`XXX で動いている セッションを監視して` と言われたら、CAO は:

1. 該当 tmux ウィンドウを探し、
2. 必要なら既存ウィンドウを明示 runner 付きで登録、
3. 見えている画面をキャプチャ、
4. 状態を推定(working / waiting / blocked / asking / finished)、
5. 安全な判断は自分で応答、
6. インパクトが大きい・曖昧な決定はあなたに確認します。

## Runner 自動検出

`bin/cao` は supervisor の環境から worker のデフォルト runner を選びます:

| supervisor | 検出方法 | worker デフォルト |
|---|---|---|
| Claude Code | `CLAUDECODE` env | `claude` |
| Codex CLI | `CODEX_HOME` env | `codex` |
| 不明 | — | `claude`(フォールバック) |

worker 単位で上書きしたい場合は `--runner`、全体で固定したい場合は `CAO_RUNNER` を:

```sh
./bin/cao add /path/to/project --runner codex     # 1つだけ codex worker を混ぜる
export CAO_RUNNER=codex                            # 以降の worker を全部 codex に
```

`cao send` は送信キー(`claude` には `C-m` / Enter、`codex` には `C-j` / Ctrl+Enter)をウィンドウに記録された runner から自動で選びます。

`cao add` で作られていない既存 tmux ウィンドウは、`cao send` で入力を送る前に明示的な runner 付きで登録する必要があります。登録済みの外部 window は `cao list` と引数なしの `cao capture` に含まれます。監督が終わったら登録解除します。

## 内部ツール

`./bin/cao` は supervisor の内部ヘルパーで、ユーザー向けではありません。

```sh
./bin/cao init
./bin/cao add /path/to/project --name project-a                   # runner は自動検出
./bin/cao add /path/to/legacy  --name project-b --runner codex    # 明示的に codex worker
./bin/cao add /path/to/proj    --name project-c --resume --prompt "続きから"
./bin/cao register other-session:window --runner codex            # 既存 tmux window
./bin/cao unregister other-session:window                         # 監督対象から外す
./bin/cao list
./bin/cao capture
./bin/cao capture project-a --lines 180
./bin/cao send project-a "Yes、その方針で進めてください。"
./bin/cao attach
./bin/cao kill
```

### 環境変数

| 変数 | デフォルト | 意味 |
|---|---|---|
| `CAO_SESSION` | `cao` | tmux session 名 |
| `CAO_RUNNER` | auto-detected | worker のデフォルト runner(`claude` または `codex`) |
| `CLAUDE_BIN` | `claude` | Claude Code コマンド |
| `CODEX_BIN` | `codex` | Codex コマンド |
| `CAO_HISTORY` | `4000` | tmux ペインの履歴行数 |
| `CAO_STATE_DIR` | `.cao` | 登録済み外部 target のローカル実行時状態 |

## Runner ごとの設定

CAO は両方の runner 用の supervisor 設定を同居させて出荷しています。互いに独立で、supervisor は自分の runner 用ファイルだけを読みます。

### Claude Code(`.claude/` + `CLAUDE.md`)

- `CLAUDE.md` — Claude Code supervisor の操作マニュアル。
- `.claude/settings.json` — permissions, env, model, hooks, statusline。
- `.claude/commands/cao-*.md` — スラッシュコマンド(`/cao-add`, `/cao-sweep`, `/cao-rescue`, `/cao-broadcast`)。
- `.claude/agents/cao-*.md` — subagent(`cao-supervisor`, `cao-rescue`)。
- `.claude/hooks/` — 監督補助(`tmux send-keys` 後の自動キャプチャ)。
- `.claude/statusline.sh` — 現在の worker 数と runner の内訳を表示。

`.claude/settings.local.json.example` を `.claude/settings.local.json` にコピーすれば個人 override が可能(gitignored)。

### Codex CLI(`.codex/` + `AGENTS.md`)

- `AGENTS.md` — Codex supervisor の操作マニュアル。
- `.codex/config.toml` — runtime の sandbox / approval policy。
- `.codex/rules/default.rules` — プロジェクトローカルのコマンドルール。

`.codex/config.toml` はデフォルトで `approval_policy = "never"` と `sandbox_mode = "danger-full-access"` を設定しています。これは Codex を supervisor として使うケースの意図的な設定で、CAO は各 worker の working tree(`git status` / `cat` / `rg`)や tmux socket を読む必要があり、これらはどちらもリポジトリ外にあるため Codex のデフォルト `workspace-write` サンドボックスではブロックされます。Codex CLI でここを動かす前に、ご自身の脅威モデルに合わせて調整してください。

同じ project config で CAO の実行時環境(`CAO_SESSION`, `CAO_RUNNER`, `CLAUDE_BIN`, `CODEX_BIN`)も固定し、このディレクトリで Codex CLI を起動したときに supervisor 用のデフォルトが揃うようにしています。

## ポリシー

ステータスファイルを追加するより、画面の直接観察を優先します。worker エージェントに報告ファイルを作らせる運用は、明示的に頼まれた場合のみにしてください。

CAO は **ユーザー意図の唯一の保持者** として振る舞います:

- ローカルで明らかな選択には自分で答える、
- ユーザーの依頼から逸脱した worker は軌道修正する、
- ownership が衝突しないよう調整する、
- インパクトの大きい選択はユーザーに上げる、
- 大事な決定と結果だけを要約する。
