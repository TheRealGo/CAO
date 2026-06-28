import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BIN_CAO = ROOT / "bin" / "cao"


def _function_body(source: str, name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{\n", source, re.MULTILINE)
    assert match, f"missing function: {name}"
    start = match.end()
    next_match = re.search(r"^\S[^\n]*\(\) \{\n", source[start:], re.MULTILINE)
    end = start + next_match.start() if next_match else len(source)
    return source[start:end]


class CaoSessionContractTests(unittest.TestCase):
    def test_cao_does_not_fallback_to_lowercase_session(self) -> None:
        source = BIN_CAO.read_text()
        detect_session = _function_body(source, "detect_session")
        self.assertNotIn("has-session -t cao", detect_session)
        self.assertNotIn("printf 'cao\\n'", detect_session)

    def test_read_and_send_commands_do_not_create_default_session(self) -> None:
        source = BIN_CAO.read_text()
        for function_name in ("cmd_list", "cmd_capture", "cmd_send"):
            body = _function_body(source, function_name)
            self.assertNotIn("ensure_session", body)
        self.assertNotIn("worker_message_guard_reason", source)
        self.assertNotIn("guard_worker_message", source)
        self.assertNotIn("_guard-message", source)

    def test_auto_compact_is_standard_dashboard_behavior(self) -> None:
        source = BIN_CAO.read_text()
        dashboard_loop = _function_body(source, "dashboard_loop")
        auto_compact_window = _function_body(source, "auto_compact_window")
        context_used_percent = _function_body(source, "context_used_percent")

        self.assertIn("AUTO_COMPACT_THRESHOLD", source)
        self.assertIn("auto_compact_sweep", dashboard_loop)
        self.assertIn('"/compact"', auto_compact_window)
        self.assertIn("runner_submit_key", auto_compact_window)
        self.assertIn('[[ "$state" == "ready" || "$state" == "idle" ]]', auto_compact_window)
        self.assertIn("pct > AUTO_COMPACT_THRESHOLD", auto_compact_window)
        self.assertIn("context[[:space:]]+used", context_used_percent)
        self.assertIn("AUTO_COMPACT_COOLDOWN", auto_compact_window)

    def test_claude_project_settings_pin_uppercase_cao_session(self) -> None:
        settings = (ROOT / ".claude" / "settings.json").read_text()
        example = (ROOT / ".claude" / "settings.local.json.example").read_text()
        statusline = (ROOT / ".claude" / "statusline.sh").read_text()

        self.assertIn('"CAO_SESSION": "CAO"', settings)
        self.assertIn("${CAO_SESSION:-CAO}", settings)
        self.assertNotIn('"CAO_SESSION": "cao"', settings)
        self.assertNotIn("${CAO_SESSION:-cao}", settings)

        self.assertIn('"CAO_SESSION": "CAO"', example)
        self.assertNotIn("has-session -t cao", statusline)

    def test_claude_settings_reinforce_recipient_discipline_on_user_prompt(self) -> None:
        settings = (ROOT / ".claude" / "settings.json").read_text()
        hook = (ROOT / ".claude" / "hooks" / "recipient_discipline_on_prompt.sh").read_text()

        self.assertIn('"UserPromptSubmit"', settings)
        self.assertIn("recipient_discipline_on_prompt.sh", settings)
        self.assertNotIn("prevent_meta_send.sh", settings)
        self.assertIn("CAO宛先判定義務", hook)
        self.assertIn("Workerへ送らない", hook)
        self.assertIn("hookEventName", hook)

    def test_codex_settings_reinforce_recipient_discipline_on_user_prompt(self) -> None:
        config = (ROOT / ".codex" / "config.toml").read_text()
        hook = (ROOT / ".codex" / "hooks" / "recipient_discipline_on_prompt.sh").read_text()

        self.assertIn("[[hooks.UserPromptSubmit]]", config)
        self.assertIn("recipient_discipline_on_prompt.sh", config)
        self.assertIn("CAO宛先判定義務", hook)
        self.assertIn("Workerへ送らない", hook)
        self.assertIn("hookEventName", hook)


if __name__ == "__main__":
    unittest.main()
