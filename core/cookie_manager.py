"""
Cookie Manager for YouTube authentication and anti-bot bypass.
Handles Netscape cookies, Base64 decoding, validation, and secure export.
"""
import os
import stat
import base64
import time
from typing import Dict, Any, List, Optional


class CookieManager:
    """Manages YouTube cookies to ensure uninterrupted video fetching via yt-dlp."""

    CRITICAL_COOKIE_KEYS = [
        "SID",
        "HSID",
        "SSID",
        "LOGIN_INFO",
        "__Secure-1PSID",
        "__Secure-3PSID",
    ]

    @staticmethod
    def decode_cookie_data(raw_data: str) -> str:
        """
        Decodes raw cookie data from either plain Netscape text or Base64 string.
        """
        if not raw_data:
            return ""

        # If it already looks like Netscape format, return directly preserving layout
        if "# Netscape HTTP Cookie File" in raw_data or "\t" in raw_data:
            return raw_data

        stripped = raw_data.strip()
        # Try base64 decoding
        try:
            decoded = base64.b64decode(stripped).decode("utf-8", errors="ignore")
            return decoded
        except Exception:
            return raw_data

    @classmethod
    def validate_cookies_content(cls, content: str) -> Dict[str, Any]:
        """
        Analyzes cookies content to detect YouTube domain cookies, presence of
        authentication session tokens, and expiration states.
        """
        if not content:
            return {
                "valid": False,
                "has_youtube": False,
                "critical_found": [],
                "expired_count": 0,
                "message": "Empty cookie content",
            }

        lines = content.splitlines()
        found_keys: List[str] = []
        expired_count = 0
        has_youtube = False
        now = time.time()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) >= 7:
                domain, flag, path, secure, expiry, name, value = parts[:7]
                if "youtube.com" in domain or "google.com" in domain:
                    has_youtube = True

                if name in cls.CRITICAL_COOKIE_KEYS:
                    found_keys.append(name)

                try:
                    exp_val = int(expiry)
                    if 0 < exp_val < now:
                        expired_count += 1
                except ValueError:
                    pass

        unique_keys = list(set(found_keys))
        is_valid = has_youtube and len(unique_keys) > 0

        return {
            "valid": is_valid,
            "has_youtube": has_youtube,
            "critical_found": unique_keys,
            "expired_count": expired_count,
            "total_lines": len(lines),
            "message": (
                f"Valid YouTube cookies with {len(unique_keys)} auth tokens"
                if is_valid
                else "Cookies do not appear to contain authenticated YouTube session tokens"
            ),
        }

    @classmethod
    def export_cookie_file(cls, cookie_data: str, target_path: str) -> str:
        """
        Writes cookie data to file with secure file permissions (0600).
        """
        decoded = cls.decode_cookie_data(cookie_data)
        if not decoded:
            raise ValueError("No cookie data provided to export.")

        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(decoded)

        # Set file permissions to owner read/write only (chmod 600)
        try:
            os.chmod(target_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

        return target_path

    @staticmethod
    def get_ytdlp_cookie_args(cookie_path: Optional[str] = None) -> List[str]:
        """
        Returns list of yt-dlp arguments for cookies if provided or if default files exist.
        """
        if cookie_path:
            return ["--cookies", cookie_path]

        # Check default paths
        for default_name in ["youtube_cookies.txt", "cookies.txt"]:
            if os.path.isfile(default_name):
                return ["--cookies", default_name]

        return []
