"""
Cookie Manager for YouTube authentication and anti-bot bypass.
Handles Netscape cookies, Base64 decoding, validation, and secure export.
"""
import os
import re
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
    def _is_youtube_or_google_domain(domain: str) -> bool:
        """Matches exact or subdomain entries for youtube.com and google.com."""
        host = domain.strip().lstrip(".").lower()
        return (
            host == "youtube.com"
            or host.endswith(".youtube.com")
            or host == "google.com"
            or host.endswith(".google.com")
        )

    @staticmethod
    def decode_cookie_data(raw_data: str) -> str:
        """
        Decodes raw cookie data from either plain Netscape text or Base64 string.
        """
        if not raw_data:
            return ""

        stripped = raw_data.strip()
        if not stripped:
            return ""

        # If it already looks like Netscape format, return directly preserving layout
        if "# Netscape HTTP Cookie File" in raw_data or "#HttpOnly_" in raw_data or "\t" in raw_data:
            return raw_data

        # Strictly validate base64 and ensure UTF-8 without control-char garbage
        compact = re.sub(r"\s+", "", stripped)
        try:
            decoded_bytes = base64.b64decode(compact, validate=True)
            decoded = decoded_bytes.decode("utf-8")
            # Reject accidental base64 decodes that emit binary control bytes
            if any(ord(ch) < 32 and ch not in ("\t", "\n", "\r") for ch in decoded):
                return raw_data
            return decoded
        except Exception:
            return raw_data

    @classmethod
    def validate_cookies_content(cls, content: str) -> Dict[str, Any]:
        """
        Analyzes cookies content to detect YouTube domain cookies, presence of
        unexpired authentication session tokens, and expiration states.
        """
        if not content or not content.strip():
            return {
                "valid": False,
                "has_youtube": False,
                "critical_found": [],
                "expired_count": 0,
                "total_lines": 0,
                "message": "Empty cookie content",
            }

        lines = content.splitlines()
        found_keys: List[str] = []
        expired_count = 0
        has_youtube = False
        now = time.time()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Strip Netscape HttpOnly prefix before skipping comments
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            elif line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) >= 7:
                domain, _flag, _path, _secure, expiry, name, value = parts[:7]
                is_yt_domain = cls._is_youtube_or_google_domain(domain)
                if is_yt_domain:
                    has_youtube = True

                is_expired = False
                try:
                    exp_val = int(expiry)
                    if 0 < exp_val < now:
                        is_expired = True
                        expired_count += 1
                except ValueError:
                    pass

                if is_yt_domain and not is_expired and value.strip() and name in cls.CRITICAL_COOKIE_KEYS:
                    found_keys.append(name)

        unique_keys = sorted(set(found_keys))
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
                else "Cookies do not appear to contain active authenticated YouTube session tokens"
            ),
        }

    @classmethod
    def export_cookie_file(cls, cookie_data: str, target_path: str) -> str:
        """
        Writes cookie data to file with secure file permissions (0600).
        """
        decoded = cls.decode_cookie_data(cookie_data)
        if not decoded or not decoded.strip():
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
        Returns list of yt-dlp arguments for cookies if provided file or default file exists.
        """
        if cookie_path:
            if os.path.isfile(cookie_path):
                return ["--cookies", cookie_path]
            return []

        # Check default paths
        for default_name in ["youtube_cookies.txt", "cookies.txt"]:
            if os.path.isfile(default_name):
                return ["--cookies", default_name]

        return []
