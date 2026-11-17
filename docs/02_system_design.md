# FÁZA 2 – Návrh systému: CFE (Confluence Futures Engine)

> Tento dokument popisuje **finálnu (v2) architektúru**, ktorá vznikla po meraniach na reálnych dátach.
> Pôvodný návrh (v1 – „klasické konfluenčné skóre“) je opísaný v kapitole 7, spolu s dôvodmi, prečo bol zmenený.
> Referenčná implementácia: `backtest/engine.py` (štruktúra, likvidita, MTF) a `backtest/cfe.py` (setup + skóre),
> Pine Script v6: `pine/CFE_indicator.pine`, `pine/CFE_strategy.pine`.

---

## 1. Architektúra

```
                 ┌──────────────────────────────────────────────────────────────┐
  OHLCV (chart)  │ A. TREND / MTF         EMA 20/50/100/200 stack → stav [-1,1]  │
  + HTF bars ───▶│    15m (w1.0) · 1h (w1.5) · 4h (w2.0) · [1D (w2.0)]          │──┐
                 │    = predošlá UZAVRETÁ HTF sviečka (bez lookahead)            │  │ kontext (filter)
                 ├──────────────────────────────────────────────────────────────┤  │
                 │ D. ŠTRUKTÚRA & LIKVIDITA (stavový automat)                   │  │
                 │    pivoty → HH/HL/LH/LL → BOS/CHoCH (na close) → impulzný leg │──┤ trigger + plán
                 │    pooly likvidity (neodobraté swingy), EQH/EQL, sweep,       │  │
                 │    FVG, order blocky, najbližšia protiľahlá likvidita         │  │
                 ├──────────────────────────────────────────────────────────────┤  │
                 │ B. OBJEM   RVOL, USD objem, odhad tlaku kupujúcich/predávajúcich│──┤
                 │ C. MOMENTUM RSI (režim, divergencia), MACD histogram          │──┤ skóre 0–100
                 │ E. VOLATILITA ATR, ATR percentil, extrémna volatilita         │──┤
                 └──────────────────────────────────────────────────────────────┘  │
                                                                                     ▼
            ┌───────────────────── SIGNAL ENGINE ─────────────────────┐   ┌──── RISK ENGINE ────┐
            │ trigger: BOS/CHoCH s displacementom v smere HTF trendu  │──▶│ Entry = prelomená   │
            │ filtre: HTF zhoda ≥ prah, cost filter, volatilita,      │   │  úroveň (limit) /   │
            │         session, skóre ≥ min                            │   │  close (market)     │
            └─────────────────────────────────────────────────────────┘   │ SL = extrém legu ±  │
                                                                            │  0,2 ATR (invalid.) │
                                                                            │ TP1/2/3 = 1/2/3 R   │
                                                                            │  (alebo likvidita)  │
                                                                            └──────────┬──────────┘
                                                                                       ▼
                              ┌──────────── TRADE TRACKER (len potvrdené sviečky) ────────────┐
                              │ PENDING LIMIT → FILLED → TP1 → (BE) → TP2 → (lock) → TP3       │
                              │ / SL / STOP / EXIT / CANCEL / EXPIRED  → alerty + dashboard     │
                              └─────────────────────────────────────────────────────────────────┘
```

## 2. Vrstvy (čo počítajú a prečo)

### A. Trend & Multi-Timeframe
* **Stav trendu** v každom TF: `T = ¼·[sgn(close−EMA50) + sgn(EMA20−EMA50) + sgn(EMA50−EMA100) + sgn(EMA100−EMA200)]` ∈ {−1, −0,5, 0, 0,5, 1}.
* **HTF alignment** = vážený priemer T z TF vyšších ako graf (15m w=1, 1h w=1,5, 4h w=2, voliteľne 1D w=2).
* **Bez lookahead:** `request.security(sym, tf, f_trend()[1], lookahead = barmerge.lookahead_on)` – vždy hodnota *predošlej uzavretej* HTF sviečky (oficiálne dokumentovaný non-repainting vzor). V Pythone identicky: `htf_state_aligned()` posúva HTF sériu o 1.
* **Nižšie TF (1m, 3m) v dashboarde:** `request.security_lower_tf` a použijú sa iba intrabary, ktoré sa **uzavreli vnútri** aktuálnej sviečky grafu (`time_close` filter) – chráni to aj nezarovnané TF (3m na 5m grafe), kde by inak vznikol únik budúcich dát. Nižšie TF sú len informačné (validácia nenašla dôvod dávať im váhu).
* Príklad zo zadania („1m LONG, ale 15m a 1h výrazne bearish“): HTF alignment je záporný → LONG setup neprejde filtrom (default vyžaduje zhodu všetkých HTF = 1,0).

### D. Market structure & likvidita (stavový automat, poradie operácií je fixné)
1. **Pivoty**: swing high = `high[L]` je maximum okna `2L+1` (L = 5). Logika ho použije až **po potvrdení** (L sviečok neskôr).
2. **HH/HL / LH/LL** sekvencia z posledných dvoch pivotov.
3. **Sweep (stop-hunt)**: knôt prekročí neodobratý pool (swing high/low), close sa vráti späť → likvidita „zobraná“. Každý pool sa spotrebuje pri prvom prekročení.
4. **BOS / CHoCH na close**: close nad posledným neprelomeným swing high = bullish break; ak bola štruktúra bearish → **CHoCH**, inak **BOS**. Zaznamená sa prelomená úroveň a **extrém impulzného legu** (najnižšie low od posledného swing low). Order block = posledná opačná sviečka v legu.
5. **FVG**: 3-sviečková medzera ≥ 0,25 ATR.
6. **Invalidácia zón** pri close za vzdialenou hranou.
7. **Najbližšia protiľahlá likvidita** (pooly + zóny) – pre adaptívne TP a filter „room“.

### B. Objem
* **RVOL** = objem / SMA(20) predošlých sviečok; **spike** pri RVOL ≥ 2.
* **Objem v USD**: `volume × close` pre `syminfo.volumetype == "base"` (resp. `volume` pre „quote“), prepočet `request.currency_rate(mena, "USD")`. Ak kurz nie je dostupný → zobrazí sa v mene kotácie (napr. USDT) a **nikdy sa nevymýšľa**.
* **Buy/sell tlak** = **ODHAD** (pozícia close v range sviečky, alebo intrabar up/down klasifikácia). V dashboarde je vždy označený „est.“.
  Skutočná delta (agresor) je dostupná len cez footprint → samostatný doplnok `CFE_footprint_delta_addon.pine` (Premium/Ultimate).
  Meranie kvality odhadu voči **skutočnej** Binance taker delte: korelácia ≈ 0,49–0,55, zhoda znamienka ≈ 70 % (viď validačný report).

### C. Momentum (vybrané len to, čo nie je redundantné)
* **RSI(14)** – režim (nie prekúpené/prepredané v smere obchodu) a pravidelná divergencia na potvrdených pivotoch.
* **MACD histogram** – zhoda smeru momenta.
* **Stochastic RSI sa nepoužíva**: je to transformácia RSI (vysoká redundancia), v návrhu by duplikoval informáciu a pridával šum.

### E. Volatilita
* ATR(14), ATR% a **percentil ATR** (500 sviečok); režim LOW/NORMAL/HIGH/EXTREME.
* **Nevhodné podmienky:** percentil > 99 (extrémne udalosti) → bez obchodu.
* **Cost filter:** SL vzdialenosť musí byť ≥ k × round-trip náklady (default k = 4 → náklady ≤ 25 % z 1R). Toto je kľúčový rozdiel oproti bežným indikátorom – pri 1–5m grafoch náklady inak tvoria 30–50 % rizika.

## 3. Signal engine – pravidlá LONG / SHORT

LONG (SHORT zrkadlovo):

| # | Podmienka | Default |
|---|---|---|
| 1 | Potvrdený **bullish BOS alebo CHoCH** na close sviečky | povolený aj CHoCH |
| 2 | **Displacement**: telo ≥ 50 % range a range ≥ 0,8 ATR, zelená sviečka | 0,5 / 0,8 |
| 3 | **HTF alignment ≥ prah** | **1,0** (všetky HTF bullish) |
| 4 | SL vzdialenosť v rozsahu 0,5–6 ATR a ≥ 4× round-trip náklady | |
| 5 | ATR percentil ≤ 99 | |
| 6 | **Session filter** (hodina uzavretia sviečky v UTC 13–24) | zapnutý |
| 7 | **Skóre ≥ min** | **70** |
| 8 | Nikdy LONG a SHORT na tej istej sviečke; nový signál len ak nie je otvorená pozícia (pending limit sa novým setupom nahradí) | |

## 4. Skóre 0–100

`skóre = 100 · Σ wᵢ·sᵢ / Σ wᵢ`, kde každá vrstva sᵢ ∈ [0,1]:

| Vrstva | Obsah sᵢ | Váha |
|---|---|---|
| Trend / MTF | 0,7·(HTF alignment) + 0,3·(lokálny trend) | **45** |
| Štruktúra | kvalita displacementu (telo, range/ATR) + HH/HL sekvencia | 15 |
| Objem | RVOL + odhad tlaku v smere | 10 |
| Momentum | RSI v „zdravom“ pásme (50–65) + MACD hist v smere | 10 |
| Likvidita | nedávny sweep v smere + nová FVG z displacementu | 10 |
| Volatilita | ATR percentil (nízky = horšie, extrém = horšie) | 10 |
| Room | priestor k protiľahlej likvidite | 0 |

**Prečo takto:** časovo oddelená kalibrácia (tréning 2022 → validácia 2023-H1) ukázala, že **iba trendová vrstva** mala konzistentne kladný koeficient; ostatné vrstvy nemali mimo-vzorkovú predikčnú hodnotu (rank-korelácia ≈ 0). Váhy preto zvýhodňujú trend. Pásma WEAK/VALID/STRONG/HIGH-CONVICTION sú **len popisné**: out-of-sample test nenašiel vyššiu očakávanú hodnotu pre vyššie pásma (viď report §6). Skóre teda **nie je pravdepodobnosť úspechu**.

## 5. Risk engine – Entry, SL, TP

* **Entry (default „Limit retest“)**: limitný príkaz na **prelomenej úrovni** (retest), platný 12 sviečok; zruší sa, ak cena dosiahne TP1 skôr než sa príkaz vyplní. Výhoda: maker poplatok, bez slippage, lepšia cena, menšie riziko. Alternatíva „Market on close“.
* **Invalidation price** = extrém impulzného legu (swing low pred BOS). **SL** = invalidácia − 0,2 ATR (min 0,5 ATR, max 6 ATR – širšie setupy sa preskočia).
* **TP1 / TP2 / TP3** = 1R / 2R / 3R (nastaviteľné) alebo **Liquidity adaptive**: TP2 sa prisunie 0,1 ATR pred najbližšiu protiľahlú likviditu, ak je 2–5R ďaleko; TP3 ≥ TP2 + 1R.
* **Riadenie**: default 33 % / 33 % / zvyšok na TP1/TP2/TP3, SL na break-even (+ náklady) po TP1, SL na TP1 po TP2, voliteľný ATR trailing.
* **EXIT**: (a) voliteľné uzavretie pri opačnom potvrdenom signáli, (b) **EXIT warning** pri CHoCH proti pozícii alebo otočení HTF trendu (default len upozornenie – automatické uzatváranie nebolo validované), (c) voliteľný time stop.
* **Náklady v R**: poplatky (taker/maker), slippage, funding – zobrazené v dashboarde a zahrnuté vo validácii (s reálnym historickým fundingom).

## 6. Non-repainting garancie

| Riziko | Riešenie |
|---|---|
| Signál na otvorenej sviečke | Všetky signály a udalosti obchodu sa vyhodnocujú iba pri `barstate.isconfirmed`. Na živej sviečke sa zobrazí iba priesvitný **PREVIEW**. |
| HTF lookahead | `f()[1]` + `lookahead_on` (predošlá uzavretá HTF sviečka). |
| Nezarovnané nižšie TF | `request.security_lower_tf` + filter `time_close` intrabaru ≤ `time_close` grafu. |
| Pivoty | Logika ich používa až po potvrdení (L sviečok); kreslenie späť v čase je len anotácia. |
| Fill/TP/SL v rámci sviečky | Rovnaký predpoklad cesty ceny ako TradingView broker emulator (open → bližší extrém → vzdialenejší → close); zmena SL platí od nasledujúcej sviečky. |
| Overenie | Python test `tests/test_no_lookahead.py`: engine spustený na dátach orezaných v čase t musí dať **identické** hodnoty pre všetky sviečky < t. Negatívna kontrola (úmyselne vložený HTF repaint) test **zhodí**. |

## 7. Vývoj návrhu (prečo nie „klasické konfluenčné skóre“)

Pôvodný návrh v1 (`backtest/engine.py`, `compute()`) kombinoval 3 triggery (sweep & reclaim, BOS/CHoCH, pullback), ručne vážené skóre zo 7 vrstiev a fixný SL z posledných 5 sviečok. Merania v návrhovom období (2022-01 – 2023-06, 8 párov, 5m/15m/1h, >300 000 kandidátov):

* Hrubá (gross) očakávaná hodnota všetkých triggerov ≈ 0 R (−0,07 až −0,01 R).
* Náklady pri market vstupoch: **0,25–0,49 R na obchod na 5m**, 0,13–0,26 R na 15m.
* Rank-korelácia vrstiev s výsledkom |ρ| < 0,06; ručne vážené skóre bolo v rámci trendových breakoutov dokonca **anti-prediktívne**.

Zmeny vo v2: (1) jediný trigger s merateľnou hodnotou – displacement break **v smere HTF trendu**, (2) **štrukturálny SL** na extréme legu (väčšia vzdialenosť → nižšie náklady v R), (3) **limit retest** vstup (maker), (4) cost filter, (5) váhy skóre podľa kalibrácie. Detailné tabuľky: `docs/03_validation_report.md` a `results/design_study.json`.

## 8. Parita Pine ↔ Python

| Prvok | Pine | Python |
|---|---|---|
| Pivot | `high[L] == ta.highest(high, 2L+1)` | max okna == high[p] |
| Pooly likvidity | pole s pevným počtom slotov, prvý prázdny slot / vyhodenie najstaršieho | identicky |
| Zóny | 5 slotov, `shift` + `push` | identicky |
| ATR / RSI / EMA | `ta.atr` (RMA) / `ta.rsi` / `ta.ema` | `indicators.py` (RMA so SMA seedom, EMA seed prvou hodnotou) |
| Percentil | `ta.percentrank` | percent predošlých `n` hodnôt ≤ aktuálnej |
| Obchod | `f_fill`, `f_walk` | `find_limit_fill`, `run_trade_ex` |

Strategy (`CFE_strategy.pine`) obsahuje engine **doslova skopírovaný** z indikátora skriptom `tools/build_strategy.py`, takže sa nemôžu rozísť.
