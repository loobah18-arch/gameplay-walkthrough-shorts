import unittest
import os
import tempfile
import base64
import time
from core.cookie_manager import CookieManager


class TestCookieManager(unittest.TestCase):
    def test_decode_plain_netscape(self):
        raw = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsecret123\n"
        decoded = CookieManager.decode_cookie_data(raw)
        self.assertEqual(decoded, raw)

    def test_decode_base64_netscape(self):
        raw = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsecret123\n"
        b64 = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
        decoded = CookieManager.decode_cookie_data(b64)
        self.assertEqual(decoded, raw)

    def test_decode_rejects_accidental_binary_from_plain_text(self):
        self.assertEqual(CookieManager.decode_cookie_data("abcd"), "abcd")

    def test_validate_cookies_valid(self):
        future = int(time.time()) + 100000
        content = (
            f"# Netscape HTTP Cookie File\n"
            f".youtube.com\tTRUE\t/\tTRUE\t{future}\tSID\tvalue1\n"
            f"#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t{future}\tLOGIN_INFO\tvalue3\n"
        )
        report = CookieManager.validate_cookies_content(content)
        self.assertTrue(report["valid"])
        self.assertTrue(report["has_youtube"])
        self.assertIn("SID", report["critical_found"])
        self.assertIn("LOGIN_INFO", report["critical_found"])
        self.assertEqual(report["expired_count"], 0)
        self.assertEqual(report["total_lines"], 3)

    def test_validate_cookies_rejects_expired_and_lookalike_domain(self):
        past = int(time.time()) - 1000
        content = (
            f"# Netscape HTTP Cookie File\n"
            f".notyoutube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tvalue1\n"
            f".youtube.com\tTRUE\t/\tTRUE\t{past}\tSID\texpired\n"
        )
        report = CookieManager.validate_cookies_content(content)
        self.assertFalse(report["valid"])
        self.assertTrue(report["has_youtube"])
        self.assertEqual(report["critical_found"], [])
        self.assertEqual(report["expired_count"], 1)

    def test_validate_cookies_empty(self):
        report = CookieManager.validate_cookies_content("")
        self.assertFalse(report["valid"])
        self.assertEqual(report["total_lines"], 0)

    def test_export_cookie_file(self):
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "test_cookies.txt")
            content = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsecret\n"
            exported = CookieManager.export_cookie_file(content, target)
            self.assertTrue(os.path.isfile(exported))
            with open(exported, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), content)


if __name__ == "__main__":
    unittest.main()
