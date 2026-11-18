# FÁZA 7 – Návod na použitie CFE (Confluence Futures Engine)

> **Pred použitím si prečítajte `docs/03_validation_report.md`.** CFE je profesionálny nástroj na plánovanie
> obchodov, ale rozsiahla validácia nenašla štatisticky preukázateľne kladnú očakávanú hodnotu po nákladoch.
> Nejde o investičné odporúčanie. Obchodovanie futures s pákou môže viesť k strate celého vkladu.

## 1. Súbory

| Súbor | Čo to je |
|---|---|
| `pine/CFE_indicator.pine` | Hlavný indikátor: signály, Entry/SL/TP čiary, štruktúra, likvidita, dashboard, alerty, webhook JSON |
| `pine/CFE_strategy.pine` | Strategy verzia (rovnaký engine) pre Strategy Tester: veľkosť pozície, páka, poplatky, slippage, partial TP, trailing, max. počet pozícií |
| `pine/CFE_footprint_delta_addon.pine` | Voliteľný doplnok: **skutočná** volume delta + CVD z footprint dát (Premium/Ultimate) |

## 2. Inštalácia v TradingView

1. Otvorte graf, napr. `BINANCE:BTCUSDT.P` (perpetual), timeframe **15m** (odporúčané – viď report).
2. Dole otvorte **Pine Editor** → *Open* → *New blank indicator*, celý obsah nahraďte obsahom `CFE_indicator.pine`.
3. **Save** → **Add to chart**.
4. Pre backtest rovnako vložte `CFE_strategy.pine` (*New blank strategy*) a otvorte **Strategy Tester**.

> Skripty nebolo možné skompilovať priamo v TradingView počas vývoja (syntax bola overená nezávislým parserom,
> logika referenčnou Python implementáciou). Ak editor nahlási chybu, pošlite text chyby a riadok – oprava býva
> jednoriadková.

**Plán TradingView:** indikátor používa ~10 `request.*` volaní (HTF, nižšie TF, kurz USD). Funguje na bežných plánoch;
nižšie TF (1m/3m) v dashboarde sú obmedzené dostupnou intrabar históriou. Footprint doplnok vyžaduje Premium/Ultimate.

## 3. Čo vidíte na grafe

| Prvok | Význam |
|---|---|
| **▲ LONG 74 / ▼ SHORT 81** (zelený/červený štítok) | Potvrdený setup na **uzavretej** sviečke. Číslo = skóre konfluencie. Text: Entry (limit) / SL / R:R. Tooltip: všetky úrovne vrátane invalidácie, triggera (BOS/CHoCH) a HTF zhody. |
| Prerušovaná sivá čiara | Entry limit (čaká na vyplnenie). Po vyplnení plná čiara. |
| Červená čiara | Stop loss (posúva sa po TP1 na break-even, po TP2 na TP1). |
| Zelené bodkované čiary | TP1, TP2, TP3. |
| **FILLED ▲/▼** | Limitný príkaz sa vyplnil – toto je skutočný vstup. |
| **TP1 / TP2 / TP3 ✓** | Dosiahnutý cieľ (čiastočný výstup podľa nastavení). |
| **SL** (červený) / **STOP** (oranžový) | Stop loss / ochranný stop po TP (BE alebo lock). |
| **✕** | Setup zrušený (cena dosiahla TP1 skôr, než sa limit vyplnil) alebo expiroval. |
| **↺** | Čakajúci limit nahradený novším setupom. |
| **EXIT?** (oranžový) | Varovanie: CHoCH proti pozícii alebo otočenie HTF trendu. Default len upozornenie. |
| **EXIT** | Pozícia uzavretá na close (ak je zapnuté automatické uzatváranie / time stop). |
| **▲ LONG if close > X / ▼ SHORT if close < Y** (hrubá prerušovaná čiara vpravo) | **Scenár** – vopred ukazuje, kde by vznikol ďalší LONG/SHORT: prelomenie poslednej neprelomenej swing úrovne uzavretím sviečky s displacementom. **READY** = povolené HTF trendom a stop filtrami; pri READY a bez otvorenej pozície sú bodkovane zobrazené aj projekcie **SL ≈** a **TP3 ≈** (optimistický cieľ). **BLOCKED** = proti HTF trendu alebo stop mimo rozsahu. Je to projekcia, nie signál. |
| **PREVIEW LONG/SHORT** (priesvitný) | Setup sa tvorí na **neuzavretej** sviečke. Nie je to signál – po uzavretí sviečky môže zmiznúť. |
| BOS / CHoCH čiary | Prelomenie štruktúry na close. |
| Bodkované horizontály | Neodobraté pooly likvidity (swing high/low). EQH/EQL = rovnaké vrcholy/dná. |
| Boxy | FVG (zelené/červené) a order blocky (OB). |
| ◆ pod/nad sviečkou | Liquidity sweep (stop hunt). |
| EMA 20/50/100/200 | Trendový kontext. |

## 4. Dashboard (pravý horný roh)

**MARKET STATUS** – Current trend (HTF alignment −1…+1) · Market structure (BULLISH/BEARISH + posledný BOS/CHoCH + HH/HL) ·
Volatility (režim, ATR %, percentil) · Volume v **USD** (alebo v mene kotácie, ak kurz nie je dostupný) · Relative volume
(+SPIKE) · Buy/Sell pressure (**odhad**, zdroj je uvedený) · MTF alignment (1m 3m 5m 15m 1h 4h: ▲ bull, ▼ bear, ■ neutrál, N/A)
· Momentum (RSI, divergencia, MACD).

**TRADING SIGNAL** – Current signal (LONG/SHORT · PENDING LIMIT / ACTIVE, alebo WAIT) · Signal strength XX/100 + pásmo ·
Entry · Stop loss · TP1/TP2/TP3 (✓ = dosiahnuté) · Risk/Reward pre TP1/TP2/TP3.

**POSITION STATUS** – Active position (% ešte otvorené) · Unrealized PnL (% a R) · Realized R + odhad nákladov (poplatky +
funding) · Current price · Distance to SL (% a R) · Distance to next TP · Last signal.

**SCENARIOS (projection, not signals)** – riadok ▲ LONG a ▼ SHORT: spúšťacia úroveň, projekcia SL a TP3 a stav READY / BLOCKED.

Kde údaj nie je dostupný, zobrazí sa **N/A** – hodnoty sa nikdy nevymýšľajú.

## 5. Nastavenia (najdôležitejšie)

| Skupina | Parameter | Default | Poznámka |
|---|---|---|---|
| ① Signal | Entry mode | Limit retest | Market = vstup na close signálnej sviečky (vyššie náklady) |
| | Min HTF trend alignment | **1,0** | všetky HTF musia súhlasiť (validované najlepšie) |
| | Min signal strength | **70** | |
| | Session filter | **13–24 UTC** | hodina uzavretia sviečky |
| | Displacement | telo ≥ 50 %, range ≥ 0,8 ATR | |
| | Limit validity | 12 sviečok | |
| | Váhy skóre | trend 45, štruktúra 15, ostatné 10, room 0 | z kalibrácie |
| ② SL/TP | SL buffer | 0,2 ATR za extrémom legu | |
| | Min/Max SL | 0,5 / 6 ATR | širšie setupy sa preskočia |
| | TP1/TP2/TP3 | 1R / 2R / 3R | Min R:R 1:2 platí pre adaptívny TP2 |
| | TP mode | Fixed R | Liquidity adaptive = TP2 pred najbližšou likviditou |
| ③ Management | Close % TP1 / TP2 | 33,3 / 33,3 (zvyšok TP3) | |
| | BE po TP1 / SL na TP1 po TP2 | áno / áno | |
| | ATR trailing | 0 (vyp.) | |
| | Close on opposite signal / on EXIT warning | nie / nie | nevalidované ako lepšie |
| ④ Costs | Taker / Maker / Slippage | 0,05 / 0,02 / 0,02 % | prispôsobte svojej burze a VIP úrovni |
| | Cost filter k | 4 | náklady ≤ 25 % z 1R |
| ⑤ MTF | Alignment TF | 15m / 1h / 4h (+1D voliteľne) | na 15m grafe sa 15m automaticky vynechá |
| | Dashboard TF | 1m 3m 5m 15m 1h 4h | nižšie TF len informačne |

**Rôzne páry:** všetky prahy sú relatívne (ATR, percentily, R), takže skript funguje na BTC aj altcoinoch bez úprav.
Validované na 24 pároch Binance USDⓈ-M.

## 5a. Rôzne timeframy

Indikátor funguje na **každom** timeframe grafu. Všetky prahy sú relatívne (ATR, R, percentily) a vyššie timeframy pre trend
sa v režime **⑤ HTF trend timeframes = Auto** (default) vyberú podľa grafu:

| Graf | HTF trend (Auto) | Session filter | Signály na pár / mesiac* | Net R / obchod* | t* |
|---|---|---|---|---|---|
| 1m–10m | 15m + 1h + 4h | áno | 5m: 6,3 | 5m: −0,066 | −3,2 |
| 15m | 1h + 4h | áno | 3,7 | −0,020 | −0,7 |
| 30m | 1h + 4h | áno | 2,3 | −0,012 | −0,3 |
| 1h | 4h + 1D | áno | 1,0 | +0,004 | 0,1 |
| 4h | 1D + 1W | nie (len grafy < 4h) | 0,5 | −0,066 | −0,9 |
| 1D | 1W + 1M | nie | netestované | – | – |

\* Holdout-1 páry, 2022-01 až 2026-10, po poplatkoch, slippage a fundingu. 5m a 15m sú pre-registrovaný test, 30m/1h/4h sú
prieskumný test (`backtest/run_timeframes.py`, `results/timeframes_holdout1.json`). Žiadny timeframe nemá štatisticky
preukázateľný zisk; 5m je preukázateľne stratový (náklady). Na 1m/3m by boli náklady v R ešte vyššie (netestované, chýbajú dáta).

V režime **Manual** si tri HTF timeframy (+ Daily) nastavíte sami. Ak žiadny nie je vyšší ako graf, ako trend sa použije
trend samotného grafu. Na grafoch ≥ 4h sa ATR percentil počíta zo 200 sviečok (aby fungoval aj týždenný graf).

## 6. Ako obchodovať signál (odporúčaný postup)

0. **Pred signálom:** sledujte scenár. Ak je ▲ LONG **READY**, viete vopred, nad ktorou úrovňou by po uzavretí sviečky vznikol LONG,
   kde by bol približne stop a kde je optimistický cieľ (TP3). Na skutočných dátach (BTCUSDT 15m, 16. 4. 2026) sa trigger scenára
   presne zhodoval so vstupom nasledujúcich signálov a projekcia SL/TP3 sa líšila o niekoľko dolárov. Nevstupujte už na scenár –
   signál potvrdí až uzavretá sviečka.

1. Signál **▲ LONG** sa objaví po uzavretí sviečky. Skontrolujte dashboard: HTF trend, volatilita (nie EXTREME), R:R.
2. Zadajte na burze **limitný príkaz** na úrovni *Entry (limit)*, so **SL** a TP1/TP2/TP3 (reduce-only) podľa štítku.
   Veľkosť pozície = (účet × riziko %) / |Entry − SL|. Odporúčané riziko ≤ 0,5 % účtu.
3. Ak cena dosiahne TP1 skôr, než sa limit vyplní (✕), setup je neplatný – príkaz zrušte.
4. Po TP1 posuňte SL na break-even (+ poplatky), po TP2 na TP1 (ak používate defaulty).
5. **EXIT?** varovanie berte ako podnet na zúženie stopu alebo manuálne uzavretie.

## 7. Alerty a webhook

### Jednoduché alerty (alertcondition)
*Create Alert* → Condition: **CFE** → vyberte udalosť:
`CFE – Confirmed LONG`, `Confirmed SHORT`, `Limit entry filled`, `Stop loss hit`, `TP1 hit`, `TP2 hit`, `TP3 hit`,
`Exit / exit warning`, `Trend reversal (HTF)`, `High-confidence setup`, `Pending order cancelled/expired`.
Správa obsahuje pár, timeframe, entry, SL, TP1–3, skóre a R:R (cez `{{plot("CFE …")}}`).

### Kompletné JSON správy pre webhook / automatizáciu
*Create Alert* → Condition: **CFE** → **Any alert() function call** → v sekcii *Notifications* zapnite **Webhook URL**.
Pri každej udalosti príde JSON, napr.:

```json
{"event":"LONG","symbol":"BTCUSDT.P","exchange":"BINANCE","tf":"15","side":"long","order":"limit",
 "entry":67250.1,"sl":66810.4,"tp1":67689.8,"tp2":68129.5,"tp3":68569.2,"score":78.4,"rr":2.00,
 "valid_bars":12,"price":67410.0,"time":1730000000000,"id":"my-bot"}
```

Hodnoty `event`: `LONG`, `SHORT`, `HIGH_CONFIDENCE`, `FILLED`, `TP1`, `TP2`, `TP3`, `SL`, `STOP_AFTER_TP`, `EXIT`,
`EXIT_WARNING`, `CANCELLED_TP1_FIRST`, `EXPIRED`, `TREND_REVERSAL`. Pole `id` sa pridá, ak vyplníte *Bot / strategy ID*.
Alerty sa odosielajú **raz pri uzavretí sviečky** (`alert.freq_once_per_bar_close`) – aj TP/SL udalosti sa vyhodnocujú
na close, aby história a realtime boli identické (na burze nech SL/TP vykonávajú vaše príkazy, nie alert).
Do *Bot ID* nevkladajte tajné kľúče – text alertu je uložený v TradingView.

Strategy verzia posiela vlastné JSON (`LONG/SHORT/FILLED/TP1/TP2/EXIT/CLOSED/...` vrátane `qty`, `q1/q2/q3`).

> Validácia nepodporuje automatické obchodovanie s očakávaním zisku. Webhook je pripravený pre budúce využitie
> (napr. po vlastnom ďalšom výskume alebo s odlišnou logikou).

## 8. Strategy Tester – nastavenie

V **Properties** strategy:

| Nastavenie | Odporúčanie |
|---|---|
| Initial capital | podľa účtu (default 10 000 USD) |
| Commission | 0,05 % (taker; emulator nevie účtovať maker zvlášť → konzervatívne) |
| Slippage | 2 ticky (default) – pri altcoinoch zvýšte |
| Margin for long/short | **100 / páka** (default 20 % = 5×) |
| Pyramiding | 3 (skutočný limit určuje vstup *Max concurrent positions*, default 1) |
| Verify price for limit orders | 1 tick (nastavené v kóde) |

Vstupy ⑩: *Sizing mode* (Risk % / % equity / fixed qty), *Risk per trade* (1 %), *Max leverage cap* (5×),
*Max concurrent positions* (1 – iba toto bolo validované), *Backtest start*.

Tabuľka vpravo dole zobrazuje štatistiky **na pozíciu** (čiastočné výstupy spojené): počet, win rate, priemerné R po
komisii, PF, čistý zisk, **odhad fundingu** a zisk po ňom, max DD, priemernú dĺžku držania a long vs. short.
Kompletné metriky (Net profit, Max drawdown, Profit factor, # trades, Avg trade, Long/Short) sú v Strategy Testeri.

Rozdiely oproti Python validácii: jeden komisný poplatok pre všetky príkazy, plnenie limitu „1 tick cez“, TP1/TP2
detekované z ceny/množstva na close, zrušenie limitu pri dotyku TP1 až na close sviečky, funding iba ako odhad.

## 9. Footprint delta doplnok (voliteľné)

Pridajte `CFE_footprint_delta_addon.pine` ako samostatný indikátor do panelu pod graf. Zobrazuje **skutočnú** deltu
(agresor buy − sell) a CVD (reset denne/týždenne). Vyžaduje plán Premium/Ultimate. Ak dáta pre sviečku neexistujú,
zobrazí sa medzera (na).

## 10. Obmedzenia (stručne)

* Žiadna konfigurácia nemá overenú kladnú očakávanú hodnotu po nákladoch; 5m je po nákladoch stratový.
* Skóre/pásma nie sú pravdepodobnosť úspechu.
* Buy/sell tlak v hlavnom indikátore je odhad (korelácia so skutočnou deltou ≈ 0,5).
* Pine skripty neboli skompilované v TradingView počas vývoja.
* Validované: Binance USDⓈ-M, 5m a 15m, 2022–2026, 1 pozícia naraz.
