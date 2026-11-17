# FÁZA 1 – Prieskum prémiových TradingView indikátorov

> **Metodická poznámka (dôležité):** Väčšina skúmaných nástrojov je *invite-only / closed-source*.
> Ich presné algoritmy nie sú verejné. Tento prehľad vychádza výhradne z **verejnej dokumentácie výrobcov,
> verejných popisov skriptov na TradingView a open-source rekonštrukcií principov**. Kde ide o odvodenie
> (nie o zdokumentovaný fakt), je to výslovne označené **[odvodené]**. Žiadny proprietárny kód nebol
> použitý ani kopírovaný. Náš systém (CFE) je postavený výhradne na verejne známych analytických princípoch.

Zdroje sú uvedené na konci dokumentu.

---

## 1. LuxAlgo – Signals & Overlays (S&O)

| Kritérium | Zistenie |
|---|---|
| **Princíp** | Adaptívny trend-following engine („Confirmation signals“) + kontrariánsky engine („Contrarian signals“), overlaye (Smart Trail, Reversal Zones, Trend Catcher/Tracer), voliteľný ML klasifikátor označujúci signály 1–4. |
| **LONG/SHORT** | Confirmation: signál „B/S“ v smere odhadnutého trendu; „+“ = silný signál (podľa dokumentácie zhoda s trendom; tretie strany uvádzajú ADX). Contrarian: signály proti trendu na odhadovaných extrémoch, „+“ pri prekúpenosti/prepredanosti. |
| **Trend / zmena trendu** | Smart Trail – trailing úroveň, ktorá sa pri trendových výkyvoch vzďaľuje od ceny (tretie strany: Supertrend-like) **[odvodené]**. Zmena trendu = prekríženie trailu. |
| **Objem** | V základnom engine sa objem výrazne neprejavuje **[odvodené z dokumentácie – objem nie je uvedený ako vstup signálu]**. |
| **Likvidita / obraty** | Reversal Zones (zóny možného obratu, typicky volatility-band koncept) **[odvodené]**. |
| **Silné stránky** | Jednoduchosť, jasné signály, filter Smart Trail, výstupné signály („x“). |
| **Slabé stránky** | V bočnom trhu typické „whipsaw“ série; filter trendu oneskoruje vstupy (dokumentácia sama uvádza, že filter môže zmeškať nový trend). |
| **Repainting** | Dokumentácia: *„Signals are confirmed at the opening of the next candle“*; signál na poslednej sviečke sa môže zmeniť → potvrdenie až po uzavretí sviečky. |
| **Scalping / intraday** | Funguje na akomkoľvek TF, ale pri nízkych TF rastie podiel šumu a poplatkov; parameter citlivosti treba prispôsobiť **[odvodené]**. |

## 2. LuxAlgo – Price Action Concepts (PAC)

| Kritérium | Zistenie |
|---|---|
| **Princíp** | Automatizované SMC/price-action koncepty: market structure (interná 5–49 a swing 50–100 sviečok), CHoCH, CHoCH+, BOS, EQH/EQL, volumetrické order blocky, breaker blocky, liquidity grabs, trendline liquidity, FVG, premium/discount. |
| **LONG/SHORT** | Nie je to „signálový“ systém – poskytuje štruktúru a zóny; vstupy si trader vyberá sám (napr. CHoCH + retest OB). |
| **Trend / zmena** | BOS = pokračovanie trendu, CHoCH = prvý náznak zmeny charakteru; CHoCH+ = CHoCH predchádzaný zlyhaným HH/LL. |
| **Objem** | Volumetrické OB: objem vnútri bloku, podiel buy/sell aktivity, podiel na celkovom objeme. |
| **Likvidita** | EQH/EQL, liquidity grabs (knôty do likvidných oblastí), trendline liquidity. |
| **Silné stránky** | Bohatý kontext, objektivizácia diskrétnych SMC pojmov. |
| **Slabé stránky** | Veľa objektov na grafe, subjektívny výber vstupu, žiadne štatistické vyhodnotenie úspešnosti. |
| **Repainting** | Dokumentácia: štruktúrne štítky v reálnom čase; swing high/low, EQH/EQL a trendline liquidity sa zobrazia **až po potvrdení swingu** (spätne). To nie je repaint signálu, ale treba to pochopiť – pivot je známy až s oneskorením. |
| **Scalping** | Interná štruktúra (krátke lookbacky) je vhodná na LTF, ale generuje veľa BOS/CHoCH. |

## 3. Market Cipher B (Crypto Face)

| Kritérium | Zistenie |
|---|---|
| **Princíp** | Oscilátorový panel: WaveTrend (vychádza z verejného LazyBear WaveTrend), Money Flow (MFI-typ oblasť), RSI, Stoch RSI, „VWAP“ oscilátora, divergencie. |
| **LONG/SHORT** | „Green dot“ = bullish WaveTrend cross (silnejší v prepredanej oblasti), „red dot“ bearish; „gold dot“ = extrémne prepredaný stav s divergenciou. Komunita odporúča potvrdenie money flow a HTF. |
| **Trend / zmena** | Momentum-based – zmena smeru vĺn; nie priamo štruktúra trendu. |
| **Objem** | Money flow oblasť (objemovo vážený tok) ako bias. |
| **Likvidita** | Nepracuje s likviditou cenových úrovní. |
| **Silné stránky** | Prehľadná vizualizácia momenta a divergencií. |
| **Slabé stránky** | Oscilátorové kríženia sú časté; v silnom trende vytvárajú predčasné kontra-signály. Bez cenových úrovní (SL/TP) – nie je to obchodný systém. |
| **Repainting** | Kríženie na otvorenej sviečke sa môže zmeniť; HTF verzie môžu repaintovať pri nesprávnom `request.security` **[odvodené – bežný problém klonov]**. |
| **Scalping** | Na 1–5m extrémne veľa bodiek; vyžaduje HTF filter. |

## 4. AlgoAlpha (prémiová sada)

| Kritérium | Zistenie |
|---|---|
| **Princíp** | Sada invite-only nástrojov (Smart Signals Assistant, ILPAC, Momentum Concepts, Backtest builder) + množstvo open-source skriptov (Supertrend varianty, order-flow, „Net Buying/Selling Flows“). Smart Signals Assistant: primárny engine trend + reversal signálov + 5 voliteľných konfluenčných filtrov. |
| **LONG/SHORT** | Trend signály a reversal signály, filtrované konfluenciou (podľa popisu). |
| **Trend** | Adaptívne trendové pásma / Supertrend-štýl **[odvodené z ich open-source skriptov]**. |
| **Objem** | Niektoré nástroje pracujú s odhadom nákupného/predajného toku (efficiency-weighted order flow). |
| **Likvidita** | ILPAC: likvidita a price-action koncepty. |
| **Silné stránky** | Modulárna konfluencia, alerty, automatizácia. |
| **Slabé stránky** | Kombinácia mnohých filtrov zvyšuje riziko preoptimalizovania; verejné štatistiky úspešnosti nie sú auditované. |
| **Repainting** | Neuvedené pre prémiové nástroje – overiť v replay režime. |

## 5. TFO – Smart Money Essentials [TFO]

| Kritérium | Zistenie |
|---|---|
| **Princíp** | SMC „essentials“: market structure, likvidita (hlavné pivoty, kde ležia stop-lossy), displacement, order blocky, premium/discount, konfluenčná tabuľka, neskôr Timeframe Continuity (TFC). |
| **LONG/SHORT** | Kontext + konfluenčná tabuľka; obchodné rozhodnutie robí trader. |
| **Trend** | Štruktúra + TFC (zhoda smeru sviečok naprieč TF). |
| **Objem** | Nie je hlavným vstupom. |
| **Likvidita** | Pivoty = pooly stop-lossov; displacement ako potvrdenie inštitucionálneho pohybu. |
| **Silné stránky** | Displacement a TFC sú objektívne merateľné; MTF kontinuita. |
| **Slabé stránky** | Bez vlastného signálového a risk enginu. |

## 6. SMC / ICT koncepty (všeobecne)

* **Princíp:** cena sa pohybuje od likvidity k likvidite; „smart money“ zbiera stop-lossy (sweep), potom vytvára displacement, FVG a OB; vstup na retest.
* **Signály:** sweep → CHoCH → retest FVG/OB (reversal) alebo BOS → retest (continuation).
* **Silné:** jasné invalidačné úrovne (logické SL), dobrý R:R.
* **Slabé:** veľa subjektivity; štatisticky sa jednotlivé prvky (FVG, OB) ťažko overujú. **Naše merania na reálnych dátach (Fáza 5) ukázali, že samotné FVG/OB/sweep znaky nemali merateľnú predikčnú hodnotu na 5m/15m/1h – užitočný bol trend kontext a štruktúrny stop.**

## 7. Volume Profile / Order Flow / CVD

* **Volume Profile:** distribúcia objemu podľa ceny (POC, VAH, VAL, HVN/LVN). Robustný koncept pre S/R a ciele. V Pine dostupné cez `request.footprint()` (Premium/Ultimate plán, jedna unikátna požiadavka na skript) alebo aproximáciou z nižšieho TF.
* **Order flow / skutočná Volume Delta:** vyžaduje informáciu o *agresorovi* každého obchodu (tick dáta). TradingView ju sprístupňuje cez footprint (`footprint.delta()`, `buy_volume()`, `sell_volume()`), ostatné „delta“ indikátory sú **odhady** (klasifikácia intrabar sviečok up/down alebo pozícia close v range).
* **CVD:** kumulatívny súčet delty – dôležitá je divergencia CVD vs. cena (absorpcia).
* **Rozlíšenie v našom systéme:** CFE zobrazuje *odhadovaný* tlak (OHLC metóda) a explicitne ho tak označuje. Pri validácii sme mali k dispozícii **skutočný taker-buy objem z Binance** a mohli sme porovnať odhad so skutočnosťou (pozri validačný report).

## 8. VWAP a Anchored VWAP

* **Princíp:** objemovo vážená priemerná cena od kotvy (session / udalosť). Inštitucionálny benchmark; ±σ pásma.
* **Signály:** reclaim/reject VWAP, pullback k AVWAP od swingu.
* **Silné:** objektívny, bez parametrov; dobrý pre intraday kontext.
* **Slabé:** pri 24/7 krypto trhu je „session“ kotva arbitrárna (UTC 00:00).

## 9. Trend / Momentum / Volatility systémy (Supertrend, UT Bot, Squeeze Momentum, ADX)

* **Princíp:** ATR-pásma (Supertrend/UT Bot), BB-in-KC squeeze (volatility contraction → expansion), ADX sila trendu.
* **Silné:** jednoduché, robustné, nerepaintujú pri potvrdení na close.
* **Slabé:** whipsaw v range; oneskorenie.

---

## Porovnávacia tabuľka

| Systém | Trend | Štruktúra | Objem | Momentum | Likvidita | Volatilita | SL/TP | Repaint riziko | Vhodnosť 1–5m |
|---|---|---|---|---|---|---|---|---|---|
| LuxAlgo S&O | ●●● | ● | ○ | ●● | ●(zóny) | ●● | ●(exits) | nízke (potvrdenie na ďalšej sviečke) | stredná |
| LuxAlgo PAC | ●● | ●●● | ●●(volum. OB) | ○ | ●●● | ○ | ○ | pivoty spätne | stredná |
| Market Cipher B | ● | ○ | ●●(money flow) | ●●● | ○ | ○ | ○ | stredné | nízka (šum) |
| AlgoAlpha | ●●● | ●● | ●● | ●● | ●● | ●● | ●● | neuvedené | stredná |
| TFO SMC | ●● | ●●● | ○ | ○ | ●●● | ● | ○ | pivoty spätne | stredná |
| Volume Profile/CVD | ○ | ○ | ●●● | ○ | ●●● | ○ | ● | nízke (footprint) | vysoká (ak sú dáta) |
| VWAP/AVWAP | ●● | ○ | ●●● | ○ | ●● | ●(σ pásma) | ● | žiadne | vysoká |
| Supertrend/Squeeze | ●●● | ○ | ○ | ●● | ○ | ●●● | ●(trail) | žiadne | stredná |

● = silné pokrytie, ○ = chýba.

## Najlepšie funkčné princípy (vstup do Fázy 2)

1. **Potvrdenie signálu na uzavretí sviečky** (LuxAlgo) + jasné PREVIEW vs. CONFIRMED.
2. **Štruktúra (BOS/CHoCH) s displacementom** (PAC/TFO) – objektívny trigger.
3. **Multi-timeframe kontinuita** (TFO TFC) – trend kontext z vyšších TF bez lookahead.
4. **Likvidita ako ciele a ako invalidácia** (SMC) – SL za štruktúrou, TP pri likvidite.
5. **Volatilita** (Supertrend/Squeeze) – ATR pre buffer SL, režim volatility.
6. **Objem** – RVOL a odhad tlaku ako kontext, pričom *skutočná delta* je dostupná len cez footprint.

## Čo žiadny z prieskumných nástrojov verejne nerieši (a CFE rieši)

* **Náklady obchodovania v R** – poplatky + slippage + funding ako podiel rizika. Naša validácia ukázala, že pri 5m vstupoch market príkazom náklady tvoria **0,13–0,15 R na obchod**, čo samo o sebe zničí väčšinu „edge“. CFE preto obsahuje **cost filter** a **limit (retest) vstup**.
* **Kalibrácia skóre na dátach** – väčšina konfluenčných skóre je ručne vážená. Naše meranie ukázalo, že ručne vážené konfluenčné skóre bolo dokonca **anti-prediktívne**. CFE váhy vychádzajú z merania.
* **Walk-forward a out-of-sample overenie** – prémiové nástroje nepublikujú auditované OOS výsledky.

---

## Zdroje

* LuxAlgo – Signals & Overlays dokumentácia: https://docs.luxalgo.com/docs/algos/signals-overlays/signals
* LuxAlgo – Signals & Overlays (TradingView): https://www.tradingview.com/script/fYHlrAoz-LuxAlgo-Signals-Overlays/
* LuxAlgo – Price Action Concepts: https://www.luxalgo.com/library/indicator/luxalgo-price-action-concepts/
* LuxAlgo – Smart Money Concepts (open-source): https://www.tradingview.com/script/CnB3fSph-Smart-Money-Concepts-LUX/
* Market Cipher B – komunitný popis: https://gainium.io/blog/vumanchu-cipher-b-indicator-explained
* VuManChu Cipher B (open-source rekonštrukcia): https://in.tradingview.com/script/Msm4SjwI-VuManChu-Cipher-B-Divergences
* AlgoAlpha – prehľad: https://www.tradingview.com/scripts/marketplace/AlgoAlpha/ , https://algodoc.onrender.com/docs/indicators
* Smart Money Essentials [TFO]: https://tr.tradingview.com/script/uHLqwH9d-Smart-Money-Essentials-TFO
* Pine `request.footprint()` (tretia strana): https://blog.traderspost.io/article/pine-script-footprint-requests
* Pine v6 migračná príručka: https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/
* Pine – Other timeframes and data: https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data
