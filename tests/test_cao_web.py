import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import cao_web


class CaoWebTests(unittest.TestCase):
    def test_infer_state_prioritizes_working(self) -> None:
        text = "Ready\n• Working (3s)"
        self.assertEqual(cao_web.infer_state(text), "working")

    def test_infer_state_detects_blocked(self) -> None:
        text = "Goal blocked (/goal resume)\nrequired next action"
        self.assertEqual(cao_web.infer_state(text), "blocked")

    def test_infer_state_treats_ready_prompt_with_judgment_waiting_as_ready(self) -> None:
        text = "判断待ち: 承認要否\n❯"
        self.assertEqual(cao_web.infer_state(text), "ready")

    def test_decision_line_extracts_latest_user_decision(self) -> None:
        text = "\n".join(
            [
                "older",
                "次に必要な判断: approve deployment",
                "noise",
                "承認待ち: run dev verification?",
            ]
        )
        self.assertEqual(cao_web.decision_line(text), "承認待ち: run dev verification?")

    def test_next_line_falls_back_to_tail(self) -> None:
        self.assertEqual(cao_web.next_line("alpha\nbeta"), "beta")

    def test_tail_excerpt_ignores_blank_lines(self) -> None:
        self.assertEqual(cao_web.tail_excerpt("a\n\nb\nc", limit=2), ["b", "c"])

    def test_wrapped_continuation_lines_are_joined(self) -> None:
        text = "\n".join(
            [
                "判断待ち: #1024 対象領域・ケース数・検索/監",
                "  査・成果物形式（U1〜U5）",
            ]
        )
        self.assertEqual(
            cao_web.decision_line(text),
            "判断待ち: #1024 対象領域・ケース数・検索/監査・成果物形式（U1〜U5）",
        )

    def test_prompt_placeholder_is_filtered(self) -> None:
        self.assertEqual(cao_web.tail_excerpt("work\n› Write tests for @filename\n› Find and fix a bug in @filename"), ["work"])

    def test_blank_line_prevents_joining_separate_paragraphs(self) -> None:
        text = "  - failure details\n  required\n\n  skip ServiceE2E"
        self.assertEqual(
            cao_web.tail_excerpt(text),
            ["  - failure details required", "  skip ServiceE2E"],
        )

    def test_extract_claude_assistant_text_uses_latest_main_text(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"type":"assistant","isSidechain":false,"message":{"role":"assistant","content":[{"type":"text","text":"old"}]}}',
                        '{"type":"assistant","isSidechain":true,"message":{"role":"assistant","content":[{"type":"text","text":"side"}]}}',
                        '{"type":"assistant","isSidechain":false,"message":{"role":"assistant","content":[{"type":"text","text":"latest"}]}}',
                    ]
                ),
                encoding="utf-8",
            )
            self.assertEqual(cao_web.extract_claude_assistant_text(path), "latest")

    def test_extract_codex_assistant_text_prefers_completed_message(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"draft"}]}}',
                        '{"type":"event_msg","payload":{"type":"task_complete","last_agent_message":"complete"}}',
                    ]
                ),
                encoding="utf-8",
            )
            self.assertEqual(cao_web.extract_codex_assistant_text(path), "complete")

    def test_text_from_content_joins_text_blocks(self) -> None:
        self.assertEqual(
            cao_web.text_from_content(
                [
                    {"type": "text", "text": "alpha"},
                    {"type": "tool_use", "name": "ignored"},
                    {"type": "output_text", "text": "beta"},
                ]
            ),
            "alpha\nbeta",
        )


if __name__ == "__main__":
    unittest.main()
