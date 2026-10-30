# -*- coding: utf-8 -*-
"""One-time interactive Google OAuth setup for direct Drive control (Windows only).

This never runs automatically at application startup. The OAuth client file is supplied
by the owner, used to authorize a Desktop/Installed App flow, then credentials are sealed
with Windows DPAPI in %LOCALAPPDATA%\\Windows-Agent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCOPES = ["https://www.googleapis.com/auth/drive"]


def main() -> int:
    if sys.platform != "win32":
        print("Run this authorization helper on the real Windows Agent.")
        return 2
    parser = argparse.ArgumentParser(description="Authorize direct Google Drive control on this Windows user account.")
    parser.add_argument("oauth_client_json", nargs="?", help="Path to the Google Desktop/Installed App OAuth client JSON downloaded from Google Cloud")
    args = parser.parse_args()
    client_path = Path(args.oauth_client_json).expanduser() if args.oauth_client_json else Path(input("Path to OAuth Desktop client JSON: ").strip().strip('"')).expanduser()
    if client_path.is_symlink() or not client_path.is_file():
        print("OAuth client JSON was not found as a regular file.")
        return 2
    try:
        client_doc = json.loads(client_path.read_text(encoding="utf-8"))
        if not isinstance(client_doc, dict) or not isinstance(client_doc.get("installed"), dict):
            raise ValueError("Expected an OAuth Desktop/Installed App client file (not Web app credentials).")
    except Exception as exc:
        print(f"Invalid OAuth client JSON: {exc}")
        return 2

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        import manager_client
        flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
        print("A Google sign-in window will open. Approve Drive access for this Windows Agent account.")
        credentials = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True, authorization_prompt_message="Open this URL to authorize the Windows Agent: {url}", success_message="Authorization complete. You may close this tab.")
        if not credentials.refresh_token:
            print("Google did not return a refresh token. Remove this app from Google Account access and authorize again.")
            return 1
        state_dir = manager_client.STATE_DIR
        state_dir.mkdir(parents=True, exist_ok=True)
        token_path = state_dir / "drive_control_oauth.bin"
        temp_path = token_path.with_suffix(".tmp")
        sealed = manager_client.dpapi_encrypt(credentials.to_json().encode("utf-8"))
        temp_path.write_bytes(sealed)
        temp_path.replace(token_path)
        print("Direct Drive OAuth token was sealed with Windows DPAPI in LocalAppData.")
        print("Restart Windows Agent to start 3-second online Drive polling. No token was printed or uploaded.")
        return 0
    except Exception as exc:
        print(f"OAuth setup failed ({type(exc).__name__}). No command was executed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
