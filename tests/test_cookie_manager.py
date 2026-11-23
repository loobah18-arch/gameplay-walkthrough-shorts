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

    def test_validate_cookies_valid(self):
        future = int(time.time()) + 100000
        content = (
            f"# Netscape HTTP Cookie File\n"
            f".youtube.com\tTRUE\t/\tTRUE\t{future}\tSID\tvalue1\n"
            f".youtube.com\tTRUE\t/\tTRUE\t{future}\tHSID\tvalue2\n"
            f".youtube.com\tTRUE\t/\tTRUE\t{future}\tLOGIN_INFO\tvalue3\n"
        )
        report = CookieManager.validate_cookies_content(content)
        self.assertTrue(report["valid"])
        self.assertTrue(report["has_youtube"])
        self.assertIn("SID", report["critical_found"])
        self.assertIn("HSID", report["critical_found"])
        self.assertEqual(report["expired_count"], 0)

    def test_validate_cookies_empty(self):
        report = CookieManager.validate_cookies_content("")
        self.assertFalse(report["valid"])

    def test_export_cookie_file(self):
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "test_cookies.txt")
            content = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tsecret\n"
            exported = CookieManager.export_cookie_file(content, target)
            self.assertTrue(os.path.isfile(exported))
            with open(exported, "r") as f:
                self.assertEqual(f.read(), content)


if __name__ == "__main__":
    unittest.main()
