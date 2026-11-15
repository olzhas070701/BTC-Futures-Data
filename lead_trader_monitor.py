import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

BASE_URL = "https://www.okx.com"
INST_TYPE = "SWAP"
ALMATY_TZ = ZoneInfo("Asia/Almaty")
CONFIG_FILE = Path("config/lead_traders.txt")
OUTPUT_DIR = Path("lead_trader_data")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "BTC-Futures-Data/1.0"})


def okx_get(path, params):
    response = SESSION.get(
        f"{BASE_URL}{path}",
        params=params,
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "0":
        raise RuntimeError(
            f"OKX API error for {path}: code={payload.get('code')} "
            f"msg={payload.get('msg')}"
        )
    return payload.get("data") or []


def load_unique_codes():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Missing {CONFIG_FILE}. Add one OKX lead-trader uniqueCode per line."
        )

    codes = []
    for raw_line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            codes.append(line)

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(codes))


def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def collect_for_trader(unique_code):
    collected = datetime.now(timezone.utc)
    base_record = {
        "collected_at_utc": collected.isoformat(timespec="seconds"),
        "collected_at_almaty": collected.astimezone(ALMATY_TZ).isoformat(timespec="seconds"),
        "uniqueCode": unique_code,
        "instType": INST_TYPE,
    }

    current = okx_get(
        "/api/v5/copytrading/public-current-subpositions",
        {"instType": INST_TYPE, "uniqueCode": unique_code, "limit": "100"},
    )
    append_jsonl(
        OUTPUT_DIR / "current_positions.jsonl",
        {**base_record, "record_type": "current_positions", "data": current},
    )

    time.sleep(0.5)

    history = okx_get(
        "/api/v5/copytrading/public-subpositions-history",
        {"instType": INST_TYPE, "uniqueCode": unique_code, "limit": "100"},
    )
    append_jsonl(
        OUTPUT_DIR / "position_history.jsonl",
        {**base_record, "record_type": "position_history", "data": history},
    )

    print(
        f"{unique_code}: current positions={len(current)}, "
        f"history records={len(history)}"
    )


def main():
    unique_codes = load_unique_codes()
    if not unique_codes:
        raise RuntimeError(
            f"No lead trader IDs configured. Add uniqueCode values to {CONFIG_FILE}."
        )

    for index, unique_code in enumerate(unique_codes):
        try:
            collect_for_trader(unique_code)
        except requests.RequestException as exc:
            print(f"Network error for {unique_code}: {exc}")
            raise
        except RuntimeError as exc:
            print(f"OKX returned an error for {unique_code}: {exc}")
            raise

        if index < len(unique_codes) - 1:
            time.sleep(0.5)


if __name__ == "__main__":
    main()
