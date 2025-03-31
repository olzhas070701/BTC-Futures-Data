import requests
import pandas as pd
import os
from datetime import datetime

CSV_FILE = "funding_basis_data.csv"

def get_spot_price():
    url = "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT"
    response = requests.get(url, timeout=10).json()
    return float(response["data"][0]["last"])

def get_futures_price():
    url = "https://www.okx.com/api/v5/market/ticker?instId=BTC-USD-SWAP"
    response = requests.get(url, timeout=10).json()
    return float(response["data"][0]["last"])

def get_open_interest():
    url = "https://www.okx.com/api/v5/public/open-interest?instId=BTC-USD-SWAP"
    response = requests.get(url, timeout=10).json()
    return float(response["data"][0]["oi"])

def get_funding_rate():
    url = "https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USD-SWAP"
    response = requests.get(url, timeout=10).json()
    return float(response["data"][0]["fundingRate"])

def get_cvd():
    url = "https://www.okx.com/api/v5/market/history-trades?instId=BTC-USDT&limit=100"
    response = requests.get(url, timeout=10).json()
    buy_volume = sum(float(t["sz"]) for t in response["data"] if t["side"] == "buy")
    sell_volume = sum(float(t["sz"]) for t in response["data"] if t["side"] == "sell")
    return buy_volume - sell_volume

if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
else:
    df = pd.DataFrame(columns=["date", "spot_price", "futures_price", "basis", "funding_rate", "open_interest", "cvd"])

spot_price = get_spot_price()
futures_price = get_futures_price()
basis = ((futures_price - spot_price) / spot_price) * 100
funding_rate = get_funding_rate()
open_interest = get_open_interest()
cvd = get_cvd()

date = datetime.utcnow().strftime('%Y-%m-%d %H:00:00')

if df.empty or date not in df["date"].values:
    new_data = pd.DataFrame([{
        "date": date,
        "spot_price": spot_price,
        "futures_price": futures_price,
        "basis": basis,
        "funding_rate": funding_rate,
        "open_interest": open_interest,
        "cvd": cvd
    }])
    df = pd.concat([df, new_data], ignore_index=True)
    df.to_csv(CSV_FILE, index=False)
    print(f"✅ Данные за {date} записаны.")
else:
    print(f"⚠️ Данные за {date} уже есть.")
