"""
Data loader for Binance USD-M futures public archive (data.binance.vision).

Downloads monthly kline ZIPs (includes REAL taker-buy volume = aggressor buy side)
and monthly funding-rate ZIPs. Files are cached locally as parquet/CSV.

Usage:
    python -m backtest.data --symbols BTCUSDT ETHUSDT --start 2022-01 --end 2026-10 --tf 5m
"""
from __future__ import annotations

import argparse
import io
import os
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import urllib.request

BASE = "https://data.binance.vision/data/futures/um/monthly"
DEFAULT_CACHE = Path(os.environ.get("CFE_DATA_DIR", Path(__file__).resolve().parent / "data_cache"))

KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]


def _months(start: str, end: str) -> list[str]:
    p = pd.period_range(start=start, end=end, freq="M")
    return [str(x) for x in p]


def _fetch(url: str, retries: int = 4) -> bytes | None:
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
            if e.code == 404:
                return None
            time.sleep(2 ** i)
        except Exception:
            time.sleep(2 ** i)
    return None


def _read_zip_csv(blob: bytes, cols: list[str] | None) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        name = z.namelist()[0]
        raw = z.read(name)
    first = raw[:200].decode(errors="ignore").split("\n")[0]
    has_header = any(c.isalpha() for c in first.replace("e", ""))  # header lines contain letters
    df = pd.read_csv(io.BytesIO(raw), header=0 if has_header else None)
    if cols is not None and not has_header:
        df.columns = cols[: df.shape[1]]
    return df


def load_klines(symbol: str, tf: str, start: str, end: str, cache: Path = DEFAULT_CACHE) -> pd.DataFrame:
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{symbol}_{tf}_{start}_{end}.parquet"
    if out.exists():
        return pd.read_parquet(out)
    frames = []
    for m in _months(start, end):
        url = f"{BASE}/klines/{symbol}/{tf}/{symbol}-{tf}-{m}.zip"
        blob = _fetch(url)
        if blob is None:
            continue
        df = _read_zip_csv(blob, KLINE_COLS)
        frames.append(df)
    if not frames:
        raise RuntimeError(f"no data for {symbol} {tf}")
    df = pd.concat(frames, ignore_index=True)
    df = df[KLINE_COLS[:11]]
    for c in ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_volume", "taker_buy_quote_volume"]:
        df[c] = df[c].astype(float)
    df["open_time"] = df["open_time"].astype(np.int64)
    # some archives use microseconds (2025+); normalise to ms
    us = df["open_time"] > 10**14
    df.loc[us, "open_time"] = df.loc[us, "open_time"] // 1000
    df = df.drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)
    df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df.to_parquet(out)
    return df


def load_funding(symbol: str, start: str, end: str, cache: Path = DEFAULT_CACHE) -> pd.DataFrame:
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{symbol}_funding_{start}_{end}.parquet"
    if out.exists():
        return pd.read_parquet(out)
    frames = []
    for m in _months(start, end):
        url = f"{BASE}/fundingRate/{symbol}/{symbol}-fundingRate-{m}.zip"
        blob = _fetch(url)
        if blob is None:
            continue
        frames.append(_read_zip_csv(blob, ["calc_time", "funding_interval_hours", "last_funding_rate"]))
    if not frames:
        return pd.DataFrame(columns=["calc_time", "last_funding_rate"])
    df = pd.concat(frames, ignore_index=True)
    df["calc_time"] = df["calc_time"].astype(np.int64)
    us = df["calc_time"] > 10**14
    df.loc[us, "calc_time"] = df.loc[us, "calc_time"] // 1000
    df["last_funding_rate"] = df["last_funding_rate"].astype(float)
    df = df.drop_duplicates("calc_time").sort_values("calc_time").reset_index(drop=True)
    df.to_parquet(out)
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["BTCUSDT"])
    ap.add_argument("--tf", default="5m")
    ap.add_argument("--start", default="2022-01")
    ap.add_argument("--end", default="2026-10")
    a = ap.parse_args()
    for s in a.symbols:
        k = load_klines(s, a.tf, a.start, a.end)
        f = load_funding(s, a.start, a.end)
        print(s, a.tf, len(k), k["time"].iloc[0], k["time"].iloc[-1], "funding rows", len(f))
