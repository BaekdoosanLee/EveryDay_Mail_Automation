import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_script(name, payload):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "input.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / name), "--input", str(path)],
            input="not-json-from-stdin",
            capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
        )


class InputFileTest(unittest.TestCase):
    def test_classify_reads_input_file(self):
        mails = [
            {"from": "a@x.com", "subject": "계약서 검토", "body": ""},
            {"from": "b@x.com", "subject": "뉴스레터", "body": ""},
        ]
        result = run_script("classify_mail.py", mails)
        self.assertEqual(result.returncode, 0, result.stderr)
        matched = json.loads(result.stdout)
        self.assertEqual([m["subject"] for m in matched], ["계약서 검토"])

    def test_log_mail_note_reads_empty_input_file(self):
        result = run_script("log_mail_note.py", [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_send_kakao_talk_skips_empty_titles_from_input_file(self):
        result = run_script("send_kakao_talk.py", {"header_prefix": "h", "titles": []})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("발송할 제목이 없습니다", result.stderr)


if __name__ == "__main__":
    unittest.main()
