# Pre-registration – second holdout test (written BEFORE running it)

Date: 2026-11-17

**Hypothesis (from walk-forward + holdout-1 regime breakdowns):** CFE setups perform better when the
market is in a *low-volatility regime*.

**Causal filter definition (identical in Python and Pine):**
daily log-return volatility over 30 days (population stdev) of the previous CLOSED daily bar must be
below its own 365-day median (also of the previous closed day).

**Data:** 8 symbols never used in design, walk-forward or holdout-1:
UNIUSDT, AAVEUSDT, XLMUSDT, ALGOUSDT, SANDUSDT, AXSUSDT, EGLDUSDT, VETUSDT – 2022-01 … 2026-10,
Binance USDⓈ-M, fees 0.05 % taker / 0.02 % maker, 0.02 % slippage, real funding.

**Configurations:** A = current defaults; B = A + low-volatility filter. Chart TFs: 5m and 15m.

**Decision rules (fixed in advance):**
1. B becomes the default only if avg net R of B > avg net R of A on BOTH 5m and 15m.
2. A configuration may be described as having positive expectancy only if avg net R > 0 with t-stat ≥ 2.0.
3. Results are reported whatever they are.
