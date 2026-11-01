## Výkon (95)

Laboratórne meranie v Chromiu (desktop 1366×900, mobil 390×844):

| Stránka | LCP desktop | LCP mobil | CLS | TBT | Prenos |
|---|---|---|---|---|---|
| `/` | 0,90 s | 0,66 s | 0,000 | 87 ms | ~138 kB |
| `/check-domain` | 0,73 s | 1,10 s | 0,000 | 0 ms | ~126 kB |
| `/how-it-works` | 1,02 s | 1,32 s | 0,000 | 0 ms | ~128 kB |
| `/premium` | 0,62 s | 1,28 s | 0,000 | 0 ms | ~127 kB |
| `/sources` | 0,94 s | 0,98 s | 0,000 | 0 ms | ~128 kB |

Výborné. Na stránku pripadá 8 až 10 požiadaviek, jeden JS bundle (45 kB gzip), žiadne písma tretích strán a nulový CLS. Jediná rezerva je veľké inline JSON na homepage (pozri technické SEO) a TTFB bez edge cache.
