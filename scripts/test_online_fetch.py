"""Test the real GW2 API fetch and adapter pipeline."""
import asyncio
import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC.parent))

from gw2_progression.analyzer import fetch_all  # noqa: E402
from gw2_progression.expert_ai.adapters import account_contents_to_runtime_payload  # noqa: E402

API_KEY = os.environ.get("GW2_API_KEY", "")


def main():
    try:
        if not API_KEY:
            raise RuntimeError("GW2_API_KEY is required for online fetch testing")
        contents = asyncio.run(fetch_all(API_KEY))
        print(f"Account: {contents.account_name}")
        print(f"Errors: {contents.errors}")
        payload = account_contents_to_runtime_payload(contents, item_limit=200)
        print(f"Entities: {payload['summary']['entities']}, Relations: {payload['summary']['relations']}")
        print(f"Items included: {payload['summary']['items_included']}/{payload['summary']['items_total']}")
        return 0
    except Exception:
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
