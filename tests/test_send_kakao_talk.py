import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import send_kakao_talk as skt


class BuildTitlePagesTest(unittest.TestCase):
    def test_every_page_fits_text_template_limit(self):
        titles = [f"[테스트] 아주 긴 제목이 들어가는 메일 번호 {i}" for i in range(20)]
        pages = skt.build_title_pages("📋 신규메일 20건 · 중요 6건 (10/24 21:00)", titles)
        for page in pages:
            self.assertLessEqual(len(page), skt.MAX_TEXT_LEN)

    def test_all_titles_numbered_continuously_across_pages(self):
        titles = [f"메일{i}" for i in range(1, 21)]
        pages = skt.build_title_pages("📋 신규메일", titles)
        numbers = [int(n) for page in pages for n in re.findall(r"^(\d+)\.", page, re.M)]
        self.assertEqual(numbers, list(range(1, 21)))
        for i, title in enumerate(titles, 1):
            self.assertTrue(any(f"{i}.{title}" in page for page in pages))

    def test_page_suffix_only_when_multiple_pages(self):
        single = skt.build_title_pages("📋 신규메일", ["a", "b"])
        self.assertEqual(len(single), 1)
        self.assertTrue(single[0].startswith("📋 신규메일\n"))

        many = skt.build_title_pages("📋 신규메일", [f"제목입니다 {i}" for i in range(30)])
        self.assertGreater(len(many), 1)
        for i, page in enumerate(many, 1):
            self.assertTrue(page.startswith(f"📋 신규메일 ({i}/{len(many)})\n"))

    def test_long_title_is_truncated(self):
        pages = skt.build_title_pages("h", ["가" * 50])
        line = pages[0].split("\n")[1]
        self.assertEqual(line, "1." + "가" * (skt.MAX_TITLE_LEN - 3) + "...")

    def test_empty_titles_returns_no_pages(self):
        self.assertEqual(skt.build_title_pages("h", []), [])


if __name__ == "__main__":
    unittest.main()
