## Výkon (95)

Laboratórne meranie v Chromiu (desktop 1366×900, mobil 390×844), 5 reprezentatívnych stránok:

| Stránka | LCP desktop | LCP mobil | CLS | TBT | Prenos |
|---|---|---|---|---|---|
| `/` | 1,50 s | 1,07 s | 0,000 | 0 ms | ~215 kB |
| `/povolania/` | 1,22 s | 1,05 s | 0,001 | 0 ms | ~190 kB |
| `/kocky/` | 1,24 s | 1,17 s | 0,000 | 160 ms (desktop, 3D) | ~340 kB |
| `/generator-npc/` | 1,06 s | 1,08 s | 0,000 | 0 ms | ~210 kB |
| `/tvorba-postavy/` | 1,04 s | 1,11 s | 0,026 | 0 ms | ~205 kB |

Všetky stránky sú hlboko v pásme „dobré“ (LCP < 2,5 s, CLS < 0,1). Žiadne chyby v konzole ani zlyhané požiadavky. LCP prvkom je text, nie obrázok. Fonty sa prednačítajú, JS je rozdelený po stránkach a ~20 požiadaviek na stránku je v poriadku.

| Závažnosť | Nález | Odporúčanie |
|---|---|---|
| Nízka | TTFB 0,57–0,82 s (meraný cez proxy, reálne pravdepodobne nižší). | Overiť v PageSpeed Insights. Pri TTFB > 0,6 s zvážiť cache HTML na Cloudflare edge. |
| Nízka | 3D kocky na desktope majú 160 ms blokovania hlavného vlákna. | 3D knižnicu načítať až po prvej interakcii alebo cez `requestIdleCallback`. |
| Info | INP sa v laboratóriu nedá zmerať. | Po nazbieraní návštevnosti sledovať CrUX alebo Search Console. |
