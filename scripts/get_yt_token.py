#!/usr/bin/env python3
"""
YouTube OAuth2 Refresh Token Generator for Secondary Channels (Termux-friendly).

Generates a refresh token scoped to upload videos & read channel analytics on
whichever Google account / YouTube channel you sign in with, using your
existing Google Cloud OAuth Client ID & Secret (or client_secrets.json).

Usage:
  python3 scripts/get_yt_token.py
  python3 scripts/get_yt_token.py --client-secrets client_secrets.json
"""

import argparse
import http.server
import json
import socketserver
import sys
import urllib.parse
from pathlib import Path
import requests

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

PORT = 8080
REDIRECT_URI = f"http://localhost:{PORT}/"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate YouTube OAuth Refresh Token")
    parser.add_argument("--client-secrets", help="Optional path to Google OAuth client_secrets.json")
    parser.add_argument("--client-id", help="Google Cloud OAuth Client ID")
    parser.add_argument("--client-secret", help="Google Cloud OAuth Client Secret")
    args = parser.parse_args()

    client_id = (args.client_id or "").strip()
    client_secret = (args.client_secret or "").strip()

    if args.client_secrets:
        data = json.loads(Path(args.client_secrets).read_text(encoding="utf-8"))
        block = data.get("installed") or data.get("web") or {}
        client_id = client_id or block.get("client_id", "")
        client_secret = client_secret or block.get("client_secret", "")

    if not client_id:
        client_id = input("Enter Google OAuth Client ID: ").strip()
    if not client_secret:
        client_secret = input("Enter Google OAuth Client Secret: ").strip()

    if not client_id or not client_secret:
        print("❌ Both Client ID and Client Secret are required.")
        return 1

    auth_params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent select_account",
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(auth_params)
    auth_code = None

    class OAuthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in query:
                auth_code = query["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authorized!</h1><p>Return to Termux now.</p>")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<h1>Authorization failed or denied.</h1>")

        def log_message(self, format, *args):
            pass

    print("\n1. Open this link in Chrome/browser and pick your TARGET YouTube channel:\n")
    print(auth_url)
    print(f"\n2. Waiting for callback on {REDIRECT_URI} ...\n")

    with socketserver.TCPServer(("127.0.0.1", PORT), OAuthHandler) as httpd:
        httpd.handle_request()

    if not auth_code:
        print("❌ Failed to capture authorization code.")
        return 1

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=15,
    )

    if resp.status_code != 200:
        print(f"❌ Token exchange failed ({resp.status_code}): {resp.text}")
        return 1

    refresh_token = resp.json().get("refresh_token")
    if not refresh_token:
        print("❌ No refresh_token returned. Revoke prior app access in Google Account & retry with prompt=consent.")
        return 1

    print("\n✅ OAuth Success! Upload these 3 secrets directly to GitHub via gh CLI:\n")
    print("  gh secret set YOUTUBE_CLIENT_ID --repo loobah18-arch/gameplay-walkthrough-shorts")
    print("  gh secret set YOUTUBE_CLIENT_SECRET --repo loobah18-arch/gameplay-walkthrough-shorts")
    print("  gh secret set YOUTUBE_REFRESH_TOKEN --repo loobah18-arch/gameplay-walkthrough-shorts")
    print(f"\nRefresh Token:\n{refresh_token}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
