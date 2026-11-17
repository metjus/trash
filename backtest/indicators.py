"""
Indicator primitives that replicate TradingView Pine Script v6 semantics
(bar-by-bar, causal, no look-ahead). Every function only uses data up to and
including bar i when producing output for bar i.
"""
from __future__ import annotations

import numpy as np
from numba import njit


@njit(cache=True)
def ema(src: np.ndarray, length: int) -> np.ndarray:
    """Pine ta.ema: alpha = 2/(len+1), seeded with the first non-NaN value."""
    out = np.full(src.shape[0], np.nan)
    a = 2.0 / (length + 1.0)
    prev = np.nan
    for i in range(src.shape[0]):
        x = src[i]
        if np.isnan(x):
            out[i] = prev
            continue
        if np.isnan(prev):
            prev = x
        else:
            prev = a * x + (1.0 - a) * prev
        out[i] = prev
    return out


@njit(cache=True)
def rma(src: np.ndarray, length: int) -> np.ndarray:
    """Pine ta.rma (Wilder): seeded with SMA of first `length` values."""
    n = src.shape[0]
    out = np.full(n, np.nan)
    a = 1.0 / length
    s = 0.0
    cnt = 0
    prev = np.nan
    for i in range(n):
        x = src[i]
        if np.isnan(prev):
            if not np.isnan(x):
                s += x
                cnt += 1
                if cnt == length:
                    prev = s / length
                    out[i] = prev
        else:
            if not np.isnan(x):
                prev = a * x + (1.0 - a) * prev
            out[i] = prev
    return out


@njit(cache=True)
def sma(src: np.ndarray, length: int) -> np.ndarray:
    n = src.shape[0]
    out = np.full(n, np.nan)
    s = 0.0
    for i in range(n):
        s += src[i]
        if i >= length:
            s -= src[i - length]
        if i >= length - 1:
            out[i] = s / length
    return out


@njit(cache=True)
def true_range(h, l, c):
    n = h.shape[0]
    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    return tr


def atr(h, l, c, length: int) -> np.ndarray:
    return rma(true_range(h, l, c), length)


@njit(cache=True)
def rsi(src: np.ndarray, length: int) -> np.ndarray:
    n = src.shape[0]
    up = np.zeros(n)
    dn = np.zeros(n)
    up[0] = np.nan
    dn[0] = np.nan
    for i in range(1, n):
        d = src[i] - src[i - 1]
        up[i] = d if d > 0 else 0.0
        dn[i] = -d if d < 0 else 0.0
    ru = rma(up, length)
    rd = rma(dn, length)
    out = np.full(n, np.nan)
    for i in range(n):
        if np.isnan(ru[i]) or np.isnan(rd[i]):
            continue
        if rd[i] == 0:
            out[i] = 100.0
        elif ru[i] == 0:
            out[i] = 0.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + ru[i] / rd[i])
    return out


def macd_hist(src, fast=12, slow=26, sig=9):
    m = ema(src, fast) - ema(src, slow)
    s = ema(m, sig)
    return m - s


@njit(cache=True)
def rolling_max(src, length):
    """Pine ta.highest(src, length): max over current bar and length-1 previous."""
    n = src.shape[0]
    out = np.full(n, np.nan)
    for i in range(length - 1, n):
        m = src[i]
        for j in range(i - length + 1, i):
            if src[j] > m:
                m = src[j]
        out[i] = m
    return out


@njit(cache=True)
def rolling_min(src, length):
    n = src.shape[0]
    out = np.full(n, np.nan)
    for i in range(length - 1, n):
        m = src[i]
        for j in range(i - length + 1, i):
            if src[j] < m:
                m = src[j]
        out[i] = m
    return out


@njit(cache=True)
def percentrank(src, length):
    """Pine ta.percentrank: % of the previous `length` values <= current value."""
    n = src.shape[0]
    out = np.full(n, np.nan)
    for i in range(length, n):
        x = src[i]
        if np.isnan(x):
            continue
        c = 0
        for j in range(i - length, i):
            if src[j] <= x:
                c += 1
        out[i] = 100.0 * c / length
    return out


@njit(cache=True)
def rolling_sum(src, length):
    n = src.shape[0]
    out = np.full(n, np.nan)
    s = 0.0
    for i in range(n):
        s += src[i]
        if i >= length:
            s -= src[i - length]
        if i >= length - 1:
            out[i] = s
    return out


def stdev(src, length):
    """Pine ta.stdev (population)."""
    m = sma(src, length)
    m2 = sma(src * src, length)
    v = np.maximum(m2 - m * m, 0.0)
    return np.sqrt(v)
