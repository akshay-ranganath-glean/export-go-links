#!/usr/bin/env python3
"""Export the current Glean Go Links inventory to CSV and JSON.

This read-only example calls Glean's paginated List Shortcuts API. Use a
Glean admin's authorized API token and the base URL for your Glean instance.
The export includes all shortcut types accessible to that admin, including
unlisted Go Links; no type filter is applied.

Before treating the output as complete, compare the number exported with the
API's totalItemCount and confirm the token is authorized for an admin
account. The export contains destination URLs and other potentially
sensitive information; handle and share the files securely.

API reference:
https://developers.glean.com/api/client-api/shortcuts/listshortcuts

Configuration:
  1. Install the dependencies: python3 -m pip install -r requirements.txt
  2. Create a .env file beside this script with these entries:
       GLEAN_BASE_URL=https://your-glean-instance
       GLEAN_API_TOKEN=your-authorized-bearer-token
  3. Keep .env private. Do not send it or commit it with the script.

Environment variables already set in the process take precedence over .env.

Run:
  python3 export_glean_golinks.py

The script writes glean_golinks_export.csv and glean_golinks_export.json next
to this script. The API calls use Python's standard library; python-dotenv is
the only additional dependency.
"""

import csv
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


# Keep page sizes moderate. The API returns a cursor for each subsequent page.
PAGE_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 60
ENDPOINT_PATH = "/rest/api/v1/listshortcuts"


def get_required_env(name: str) -> str:
    """Read a required environment variable without exposing its value."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set.")
    return value


def fetch_page(base_url: str, token: str, cursor: str | None) -> dict[str, Any]:
    """Fetch one read-only page of shortcuts from the Glean API."""
    url = base_url.rstrip("/") + ENDPOINT_PATH
    payload = {"pageSize": PAGE_SIZE}

    # Send the cursor returned by the previous page; omit it on the first call.
    if cursor:
        payload["cursor"] = cursor

    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    # This endpoint lists shortcuts; it does not create, update, or delete them.
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_all_shortcuts(
    base_url: str, token: str
) -> tuple[list[dict[str, Any]], int | None]:
    """Follow every API cursor and return all shortcuts plus the reported total."""
    all_shortcuts: list[dict[str, Any]] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    expected_total: int | None = None
    page_number = 0

    while True:
        page_number += 1
        page = fetch_page(base_url, token, cursor)

        shortcuts = page.get("shortcuts")
        if not isinstance(shortcuts, list):
            raise RuntimeError("The API response did not contain a shortcuts list.")
        if not all(isinstance(item, dict) for item in shortcuts):
            raise RuntimeError("The API returned a shortcut record in an unexpected format.")

        metadata = page.get("meta") or {}
        if expected_total is None and metadata.get("totalItemCount") is not None:
            expected_total = int(metadata["totalItemCount"])

        all_shortcuts.extend(shortcuts)
        print(f"Fetched page {page_number}: {len(shortcuts)} records")

        # Stop only when the API says there are no more results.
        if not metadata.get("hasNextPage", False):
            break

        next_cursor = metadata.get("cursor")
        if not next_cursor:
            raise RuntimeError(
                "The API says another page exists but returned no cursor; "
                "stopping to avoid an incomplete export."
            )
        next_cursor = str(next_cursor)
        if next_cursor in seen_cursors or next_cursor == cursor:
            raise RuntimeError("The API repeated a pagination cursor; stopping safely.")

        seen_cursors.add(next_cursor)
        cursor = next_cursor

    return all_shortcuts, expected_total


def csv_value(value: Any) -> str:
    """Convert API values to CSV cells while preserving nested data as JSON."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def write_exports(
    shortcuts: list[dict[str, Any]], output_dir: Path
) -> tuple[Path, Path]:
    """Write JSON copies of all returned records and a CSV with every API field."""
    json_path = output_dir / "glean_golinks_export.json"
    csv_path = output_dir / "glean_golinks_export.csv"

    # JSON preserves the full API response records as structured data.
    with json_path.open("w", encoding="utf-8") as json_file:
        json.dump(shortcuts, json_file, ensure_ascii=False, indent=2)
        json_file.write("\n")

    # Build a union of keys so optional fields are not dropped from the CSV.
    fieldnames: list[str] = []
    seen_fields: set[str] = set()
    for shortcut in shortcuts:
        for field in shortcut:
            if field not in seen_fields:
                seen_fields.add(field)
                fieldnames.append(field)

    with csv_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        if fieldnames:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for shortcut in shortcuts:
                writer.writerow({key: csv_value(value) for key, value in shortcut.items()})
        # If no records were returned, leave an empty CSV rather than inventing a schema.

    return csv_path, json_path


def main() -> int:
    """Load local secrets, run the export, and report the API count."""
    try:
        # Load the .env file beside this script; existing environment values win.
        env_file = Path(__file__).resolve().parent / ".env"
        load_dotenv(dotenv_path=env_file, override=False)

        base_url = get_required_env("GLEAN_BASE_URL")
        token = get_required_env("GLEAN_API_TOKEN")
        output_dir = Path(__file__).resolve().parent

        shortcuts, expected_total = fetch_all_shortcuts(base_url, token)
        csv_path, json_path = write_exports(shortcuts, output_dir)

        print(f"Exported {len(shortcuts)} shortcuts.")
        if expected_total is not None:
            print(f"API totalItemCount: {expected_total}")
            if len(shortcuts) != expected_total:
                print(
                    "WARNING: Exported row count does not match totalItemCount. "
                    "Do not treat this export as complete until the discrepancy "
                    "is investigated."
                )

        print(f"CSV:  {csv_path}")
        print(f"JSON: {json_path}")
        return 0

    except HTTPError as error:
        # Include the API's response body for troubleshooting, but never print the token.
        response_body = error.read().decode("utf-8", errors="replace")
        print(f"Glean API returned HTTP {error.code}: {response_body}", file=sys.stderr)
        return 1
    except URLError as error:
        print(f"Could not connect to the Glean API: {error.reason}", file=sys.stderr)
        return 1
    except (RuntimeError, ValueError) as error:
        print(f"Export failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
