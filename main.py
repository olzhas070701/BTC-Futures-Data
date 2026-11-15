import csv
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

BASE_URL = "https://www.okx.com"
SPOT_INST_ID = "BTC-USDT"
SWAP_INST_ID = "BTC-USDT-SWAP"
OUTPUT_FILE = Path("market_snapshot_data.csv")
ALMATY_TZ = ZoneInfo("Asia/Almaty")
FIELDS = [
    "collected_at_utc",
    "collected_at_almaty",
    "spot_inst_id",
    "spot_price",
    "swap_inst_id",
    "swap_price",
    "basis_usd",
    "basis_pct",
    "open_interest_contracts",
    "open_interest_btc",
    "open_interest_usd",
    "funding_rate",
    "funding_time_ms",
    "spot_ticker_ts_ms",
    "swap_ticker_ts_ms",
    "open_interest_ts_ms",
    "funding_response_ts_ms",
]


def okx_get(path, params):
    response = requests.get(
        f"{BASE_URL}{path}",
        params=params,
        timeout=20,
        headers={"User-Agent": "BTC-Futures-Data/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "0":
        raise RuntimeError(
            f"OKX API error for {path}: code={payload.get('code')} "
            f"msg={payload.get('msg')}"
        )
    data = payload.get("data") or []
    if not data:
        raise RuntimeError(f"OKX returned empty data for {path}")
    return data


def get_ticker(inst_id):
    return okx_get(
        "/api/v5/market/ticker",
        {"instId": inst_id},
    )[0]


def get_open_interest():
    return okx_get(
        "/api/v5/public/open-interest",
        {"instType": "SWAP", "instId": SWAP_INST_ID},
    )[0]


def get_funding_rate():
    return okx_get(
        "/api/v5/public/funding-rate",
        {"instId": SWAP_INST_ID},
    )[0]


def append_snapshot(row):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    exists = OUTPUT_FILE.exists()

    # Avoid duplicate rows if a scheduled workflow is retried in the same minute.
    if exists:
        with OUTPUT_FILE.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            if any(item.get("collected_at_utc") == row["collected_at_utc"] for item in reader):
                print(f"Snapshot already exists for {row['collected_at_utc']}; skipping.")
                return

    with OUTPUT_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        if not exists or OUTPUT_FILE.stat().st_size == 0:
            writer.writeheader()
        writer.writerow(row)


def main():
    spot = get_ticker(SPOT_INST_ID)
    swap = get_ticker(SWAP_INST_ID)
    oi = get_open_interest()
    funding = get_funding_rate()

    spot_price = float(spot["last"])
    swap_price = float(swap["last"])
    basis_usd = swap_price - spot_price
    basis_pct = (basis_usd / spot_price) * 100 if spot_price else 0.0

    now = datetime.now(timezone.utc)
    row = {
        "collected_at_utc": now.isoformat(timespec="minutes"),
        "collected_at_almaty": now.astimezone(ALMATY_TZ).isoformat(timespec="seconds"),
        "spot_inst_id": SPOT_INST_ID,
        "spot_price": spot_price,
        "swap_inst_id": SWAP_INST_ID,
        "swap_price": swap_price,
        "basis_usd": basis_usd,
        "basis_pct": basis_pct,
        "open_interest_contracts": oi.get("oi", ""),
        "open_interest_btc": oi.get("oiCcy", ""),
        "open_interest_usd": oi.get("oiUsd", ""),
        "funding_rate": funding.get("fundingRate", ""),
        "funding_time_ms": funding.get("fundingTime", ""),
        "spot_ticker_ts_ms": spot.get("ts", ""),
        "swap_ticker_ts_ms": swap.get("ts", ""),
        "open_interest_ts_ms": oi.get("ts", ""),
        "funding_response_ts_ms": funding.get("ts", ""),
    }
    append_snapshot(row)
    print(
        f"Saved {SWAP_INST_ID}: price={swap_price}, "
        f"OI USD={row['open_interest_usd']}, funding={row['funding_rate']}"
    )


if __name__ == "__main__":
    main()
