# CFE — Confluence Futures Engine

Vlastný, nerepaintujúci TradingView systém (Pine Script v6) pre kryptomenové futures: **LONG / SHORT signály,
Entry, Stop Loss, TP1/TP2/TP3, Risk/Reward, invalidácia, EXIT varovania, dashboard, alerty s webhook JSON**,
samostatná **Strategy** verzia na backtest a kompletná **Python validácia** na reálnych dátach Binance Futures
(walk-forward, out-of-sample, dva nezávislé holdout testy, poplatky + slippage + reálny funding).

## ⚠️ Výsledok validácie – najprv toto

Na 24 pároch Binance USDⓈ-M (≈12 mil. 5m sviečok, 2022-01 až 2026-10) **sa nenašla konfigurácia so štatisticky
preukázateľne kladnou očakávanou hodnotou po započítaní nákladov**:

| Default konfigurácia, páry nikdy nepoužité pri vývoji | Obchody | Win rate | Gross R/obchod | **Net R/obchod** | t-stat |
|---|---|---|---|---|---|
| 15m – holdout-1 (ADA, LTC, DOT, ATOM, NEAR, FIL, TRX, ETC) | 1 733 | 50,9 % | +0,028 | **−0,020** | −0,74 |
| 15m – holdout-2 (UNI, AAVE, XLM, ALGO, SAND, AXS, EGLD, VET) | 1 868 | 50,2 % | +0,021 | **−0,021** | −0,78 |
| 5m – holdout-1 | 2 905 | 50,0 % | +0,001 | **−0,066** | −3,18 |
| 5m – holdout-2 | 3 236 | 50,5 % | +0,006 | **−0,059** | −2,99 |

CFE je preto dodaný ako **profesionálny nástroj na analýzu a plánovanie obchodov**, nie ako overený ziskový
automatický systém. 5m scalping s ním je po nákladoch stratový; 15m je približne na nule. Detaily, metodika
a všetky tabuľky: [`docs/03_validation_report.md`](docs/03_validation_report.md). Žiadne čísla nie sú vymyslené –
všetky generujú skripty v `backtest/` a sú uložené v `results/`.

## Obsah repozitára

```
pine/
  CFE_indicator.pine              hlavný indikátor (signály, SL/TP, štruktúra, likvidita, dashboard, alerty)
  CFE_strategy.pine               strategy verzia (generovaná z indikátora: tools/build_strategy.py)
  CFE_footprint_delta_addon.pine  voliteľne: skutočná volume delta + CVD (footprint, Premium/Ultimate)
docs/
  01_research_premium_indicators.md   Fáza 1 – prieskum a porovnanie prémiových indikátorov
  02_system_design.md                 Fáza 2 – architektúra, skóre, pravidlá, non-repaint garancie
  03_validation_report.md             Fázy 5–6 – backtest, walk-forward, OOS, holdouty, režimy, náklady
  04_user_guide.md                    Fáza 7 – inštalácia, nastavenia, alerty/webhook, strategy tester
backtest/                            referenčná Python implementácia + validačné skripty
  data.py        sťahovanie Binance Futures dát (klines s taker-buy objemom, funding)
  indicators.py  EMA/RMA/ATR/RSI/MACD/percentrank so sémantikou Pine
  engine.py      štruktúra, likvidita, MTF bez lookahead (+ pôvodný engine v1)
  cfe.py         finálny setup + skóre engine (v2) = logika Pine indikátora
  sim.py         simulátor obchodov (limit/market, partial TP, BE, trailing, poplatky, slippage, funding)
  design_study.py, walkforward.py, evaluate.py, run_final.py, run_holdout2.py
tests/          no-lookahead test (+ negatívna kontrola), cross-check simulátora
results/        všetky výsledky (JSON, CSV obchodov, grafy equity, pre-registrácia)
tools/          build_strategy.py
```

## Rýchly štart (TradingView)

1. Graf `BINANCE:BTCUSDT.P` (alebo iný perpetual), odporúčaný TF **15m**.
2. Pine Editor → nový indikátor → vložiť `pine/CFE_indicator.pine` → *Add to chart*.
3. Alerty: *Create Alert* → *CFE* → konkrétna udalosť, alebo **Any alert() function call** pre JSON webhook.
4. Backtest: vložiť `pine/CFE_strategy.pine` ako strategy, v *Properties* nastaviť kapitál, komisiu, slippage
   a *Margin* = 100 / páka.

Podrobne v [`docs/04_user_guide.md`](docs/04_user_guide.md).

## Ako systém funguje (stručne)

* **Kontext:** trend z EMA 20/50/100/200 na 15m/1h/4h (predošlá *uzavretá* HTF sviečka) – LONG len ak všetky HTF bullish.
* **Trigger:** potvrdený BOS/CHoCH na close s **displacementom** (telo ≥ 50 % range, range ≥ 0,8 ATR).
* **Plán:** limit **retest** prelomenej úrovne, SL za extrémom impulzného legu (+0,2 ATR), TP 1R/2R/3R alebo pred likviditou.
* **Filtre:** cost filter (náklady ≤ 25 % z 1R), extrémna volatilita, session 13–24 UTC, skóre ≥ 70.
* **Skóre 0–100:** váhy z kalibrácie na dátach (trend 45 %) – nie je to pravdepodobnosť úspechu.
* **Non-repaint:** všetko len na potvrdených sviečkach, PREVIEW na živej sviečke, overené testom v Pythone.

## Reprodukcia validácie

```bash
pip install -r backtest/requirements.txt
export PYTHONPATH=. CFE_DATA_DIR=./data_cache
python -m backtest.data --symbols BTCUSDT ETHUSDT ... --tf 5m --start 2022-01 --end 2026-10
python -m pytest -q tests/
python -m backtest.walkforward --tf 15m --out wf
python -m backtest.run_final --wf wf --out results
```
Úplný postup v [`docs/03_validation_report.md` §10](docs/03_validation_report.md#10-reprodukcia).

## Upozornenie

Nejde o investičné poradenstvo. Obchodovanie futures s pákou je vysoko rizikové. Minulé výsledky nezaručujú budúce.
