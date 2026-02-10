#!/usr/bin/env python3
"""Helix Watcher GitHub Action entrypoint.

Sends PR context to the Helix API for scope-creep and design compliance checking.
"""

import json
import os
import sys

import httpx

HELIX_API_URL = os.environ.get("HELIX_API_URL", "http://localhost:8000")
HELIX_API_KEY = os.environ.get("HELIX_API_KEY", "")
PROJECT_ID = os.environ.get("HELIX_PROJECT_ID", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
PR_NUMBER = os.environ.get("PR_NUMBER", "")
REPO_NAME = os.environ.get("REPO_NAME", "")


def main():
    """Send webhook payload to Helix API."""
    if not PR_NUMBER or not REPO_NAME:
        print("ERROR: PR_NUMBER and REPO_NAME are required")
        sys.exit(1)

    print(f"Helix Watcher: Checking PR #{PR_NUMBER} in {REPO_NAME}")
    print(f"  API: {HELIX_API_URL}")
    print(f"  Project: {PROJECT_ID}")

    # Build a simplified webhook payload
    payload = {
        "action": "opened",
        "number": int(PR_NUMBER),
        "pull_request": {
            "number": int(PR_NUMBER),
        },
        "repository": {
            "full_name": REPO_NAME,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": HELIX_API_KEY,
        "X-GitHub-Event": "pull_request",
    }

    try:
        response = httpx.post(
            f"{HELIX_API_URL}/api/webhooks/github",
            json=payload,
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        print(f"Helix response: {json.dumps(result, indent=2)}")
        print("Scope check triggered successfully!")
    except httpx.HTTPStatusError as e:
        print(f"ERROR: Helix API returned {e.response.status_code}")
        print(f"  Body: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to contact Helix API: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
