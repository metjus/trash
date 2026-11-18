# CFE – import do TradingView (krok za krokom)

## Čo je v balíku

| Súbor | Načo | Povinný |
|---|---|---|
| `CFE_indicator.pine` | Hlavný indikátor: signály LONG/SHORT, Entry/SL/TP, scenáre, dashboard, alerty | **áno** |
| `CFE_strategy.pine` | Verzia na backtest v Strategy Testeri | voliteľne |
| `CFE_footprint_delta_addon.pine` | Skutočná volume delta (len plán Premium/Ultimate) | voliteľne |

Súbory `.pine` sú obyčajný text. Otvoríte ich v Poznámkovom bloku (Windows: pravé tlačidlo → *Otvoriť pomocou* → *Poznámkový blok*) alebo v TextEdit (Mac).

## 1. Import indikátora (5 minút, na počítači)

Pine Editor je len vo webovej verzii a v desktopovej aplikácii TradingView, nie v mobile.

1. Otvorte **tradingview.com** a prihláste sa. Otvorte graf (*Supercharts*).
2. Vľavo hore zadajte symbol, napr. **`BINANCE:BTCUSDT.P`** (perpetual futures), a timeframe **15m**.
3. Otvorte **Pine Editor** (záložka dole pod grafom, alebo ikona `{ }` v pravom/spodnom paneli).
4. Vytvorte nový prázdny indikátor: v Pine Editore kliknite na názov skriptu / ponuku → **Create new** → **Indicator**.
5. V editore označte všetko (**Ctrl+A**, Mac **Cmd+A**) a zmažte.
6. Otvorte `CFE_indicator.pine` v Poznámkovom bloku → **Ctrl+A** → **Ctrl+C** → vráťte sa do Pine Editora → **Ctrl+V**.
   Prvý riadok musí byť komentár `// This Pine Script® code…` a niekde hore `//@version=6`.
7. Uložte: **Ctrl+S** → názov napr. **CFE**.
8. Kliknite **Add to chart** (Pridať do grafu).

### Ako spoznáte, že funguje
- Vpravo hore je **dashboard** (MARKET STATUS / TRADING SIGNAL / POSITION STATUS / SCENARIOS).
- Na grafe sú čiary EMA, značky **BOS/CHoCH**, bodkované úrovne likvidity a vpravo hrubá prerušovaná čiara **scenára** („▲ LONG if close > …“).
- V histórii sa občas objaví zelený **▲ LONG** alebo červený **▼ SHORT** štítok. Je ich málo: na 15m približne 1 týždenne na pár. Väčšinu času je v dashboarde **WAIT**.

### Ak sa objaví chyba
Dole v Pine Editore sa zobrazí červená správa s **číslom riadku**. Skopírujte celú správu (aj číslo riadku) a pošlite mi ju, oprava býva jednoriadková.
Skripty boli skontrolované automaticky (syntax, linter, testy logiky), ale TradingView kompilátor nebol z vývojového prostredia dostupný. Prvé uloženie v Pine Editore je teda prvá skutočná kompilácia.

Ak je indikátor pomalý (hláška o čase výpočtu), v nastaveniach vypnite **⑤ Analyse lower TFs** a **⑧ FVG / order-block zones**.

## 2. Nastavenia (ozubené koliesko pri názve indikátora)

Väčšinu nechajte na defaultoch, tie vyšli z testov najlepšie. Zmeňte len:
- **④ Costs:** poplatky podľa vašej burzy a VIP úrovne (default Binance: taker 0,05 %, maker 0,02 %, slippage 0,02 %).
- **⑧ Display:** čo chcete vidieť (dashboard, scenáre, zóny…), pozícia dashboardu.
- **⑨ Alerts:** ak chcete JSON pre webhook a ID bota.

Všetkých 88 nastavení je popísaných v `docs/04_user_guide.md`.

## 3. Alerty (upozornenia na mobil/e-mail)

1. Ikona **budíka** (Alerts) vpravo, alebo **Alt+A** → **Create alert**.
2. **Condition:** vyberte **CFE** a potom udalosť:
   - **CFE – Confirmed LONG** / **CFE – Confirmed SHORT** (signál po uzavretí sviečky)
   - **CFE – Limit entry filled**, **TP1/TP2/TP3 hit**, **Stop loss hit**, **Exit / exit warning**, **Trend reversal (HTF)**, **High-confidence setup**
   - alebo **Any alert() function call**: jeden alert pre všetky udalosti, s kompletnou správou (JSON pre webhook).
3. **Notifications:** zapnite *Notify in app* (mobilná aplikácia TradingView), prípadne e-mail alebo *Webhook URL*.
4. **Create.** Počet aktívnych alertov závisí od vášho plánu TradingView.

## 4. Strategy (backtest) – voliteľné

1. Pine Editor → **Create new** → **Strategy** → zmazať → vložiť `CFE_strategy.pine` → **Ctrl+S** → **Add to chart**.
2. Dole otvorte záložku **Strategy Tester** (výsledky: Net profit, Max drawdown, Profit factor, zoznam obchodov).
3. Ozubené koliesko → **Properties**: *Initial capital*, *Commission* (0,05 %), *Slippage*, **Margin for long/short = 100 / páka** (20 % = 5×).
4. **Inputs → ⑩**: riziko na obchod (default 1 %), limit páky, max. počet pozícií (1 – iba toto bolo validované).

Na grafe nemajte naraz indikátor aj strategy, ak ste na bezplatnom pláne s limitom indikátorov. Na sledovanie stačí indikátor.

## 5. Mobil

Skript vytvorený na počítači sa uloží do vášho účtu. V mobilnej aplikácii ho pridáte cez **Indikátory → Moje skripty (My scripts)**. Alerty vytvorené na počítači chodia aj do mobilu.

## 6. Ako signál čítať (stručne)

1. **WAIT** = nerobiť nič. Scenár ukazuje, nad/pod akou úrovňou by vznikol LONG/SHORT.
2. **PREVIEW** (priesvitný) = sviečka sa ešte tvorí, nie je to signál.
3. **▲ LONG / ▼ SHORT** na práve uzavretej sviečke = signál. Na burze zadajte **limitný príkaz** na cene *Entry (limit)*, so SL a TP1–TP3 z dashboardu.
4. **✕** = setup zrušený (limit sa nevyplnil do 12 sviečok alebo cena skôr dosiahla TP1).

## Dôležité

Validácia na 24 pároch (2022–2026, s poplatkami a fundingom) **nenašla preukázateľne ziskovú konfiguráciu**: 15m je približne na nule, 5m je v strate. Používajte CFE ako nástroj na plánovanie a disciplínu, s malým rizikom (≤ 0,5 % účtu na obchod). Nejde o investičné odporúčanie. Detaily: `docs/03_validation_report.md`.
