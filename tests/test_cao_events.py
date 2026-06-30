import json
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "cao-events"


def _function_body(source: str, name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{\n", source, re.MULTILINE)
    assert match, f"missing function: {name}"
    start = match.end()
    next_match = re.search(r"^\S[^\n]*\(\) \{{\n", source[start:], re.MULTILINE)
    end = start + next_match.start() if next_match else len(source)
    return source[start:end]


class CaoEventsTests(unittest.TestCase):
    def run_script(self, tmp: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        state_dir = tmp / "state"
        event_log = state_dir / "events.local.jsonl"
        env = {
            **os.environ,
            "CAO_STATE_DIR": str(state_dir),
            "CAO_EVENT_LOG": str(event_log),
        }
        return subprocess.run(
            [str(SCRIPT), *args],
            check=check,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_emit_writes_local_jsonl_with_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            self.run_script(tmp, "emit", "activity", "session", "@1", "%2", "worker")

            state_dir = tmp / "state"
            event_log = state_dir / "events.local.jsonl"
            rows = event_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 1)
            row = json.loads(rows[0])
            self.assertEqual(row["event"], "activity")
            self.assertEqual(row["session"], "session")
            self.assertEqual(row["window_id"], "@1")
            self.assertEqual(row["pane_id"], "%2")
            self.assertEqual(row["window_name"], "worker")
            self.assertIsInstance(row["ts"], int)
            self.assertEqual(stat.S_IMODE(state_dir.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(event_log.stat().st_mode), 0o600)

    def test_show_tail_and_clear_are_safe_without_tmux(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            self.run_script(tmp, "emit", "activity", "session", "@1", "%1", "first")
            self.run_script(tmp, "emit", "silence", "session", "@1", "%1", "second")

            shown = self.run_script(tmp, "show", "--tail", "1").stdout.strip()
            self.assertEqual(json.loads(shown)["event"], "silence")

            self.run_script(tmp, "clear")
            event_log = tmp / "state" / "events.local.jsonl"
            self.assertEqual(event_log.read_text(encoding="utf-8"), "")
            self.assertEqual(stat.S_IMODE(event_log.stat().st_mode), 0o600)

    def test_show_missing_log_is_quiet_without_tmux(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            result = self.run_script(Path(tmp_raw), "show")
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")

    def test_invalid_numeric_options_fail_before_tmux_is_needed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            show = self.run_script(tmp, "show", "--tail", "0", check=False)
            self.assertNotEqual(show.returncode, 0)
            self.assertIn("--tail must be a positive integer", show.stderr)

            install = self.run_script(tmp, "install", "--silence", "abc", check=False)
            self.assertNotEqual(install.returncode, 0)
            self.assertIn("--silence must be a positive integer", install.stderr)
            self.assertNotIn("tmux is required", install.stderr)

    def test_hook_command_is_absolute_and_preserves_local_log_paths(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        hook_command = _function_body(source, "hook_command")
        install = _function_body(source, "cmd_install")
        remove = _function_body(source, "cmd_remove")

        self.assertIn('SCRIPT="$ROOT/bin/cao-events"', source)
        self.assertIn("CAO_STATE_DIR=%q", hook_command)
        self.assertIn("CAO_EVENT_LOG=%q", hook_command)
        self.assertIn("%q emit %q", hook_command)
        self.assertIn('set-hook -t "$SESSION" alert-activity', install)
        self.assertIn('set-hook -t "$SESSION" alert-silence', install)
        self.assertIn("$(hook_command activity)", install)
        self.assertNotIn("set-hook -g alert-activity", install)
        self.assertNotIn("pane-died", install)
        self.assertIn('set-hook -u -t "$SESSION" alert-activity', remove)
        self.assertNotIn("set-hook -gu", remove)

    def test_source_does_not_embed_private_local_names(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8") + Path(__file__).read_text(encoding="utf-8")
        private_root_marker = "/" + "Users" + "/"
        self.assertNotIn(private_root_marker, source)
        home_name = Path.home().name
        if len(home_name) >= 4:
            self.assertNotIn(home_name, source)


if __name__ == "__main__":
    unittest.main()
