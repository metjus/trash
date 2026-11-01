# Akčný plán: scopeflux.io

Aktuálne skóre **75/100**. Body 1 až 9 by ho mali posunúť na ~88. Najväčší rastový potenciál majú TLD stránky (bod 6).

## Kritické
Žiadne. Nič neblokuje indexáciu a nehrozí penalizácia.

## Vysoká priorita (do týždňa)
1. **`www` → apex:** DNS záznam `www` (proxied) a v Cloudflare presmerovanie 301 so zachovaním cesty. *(15 min, robíš ty)*
2. **Overiť Search Console a Bing Webmaster Tools:** import z GSC, kontrola sitemapy a indexácie. *(30 min, robíš ty)*
3. **SSR zoznamu:** prvých 50 až 100 riadkov do HTML namiesto „Loading…“ a inline JSON zmenšiť na prvú stranu. *(agent, 3–5 h)*
4. **Predvolené zoradenie a spam filter:** prvá strana bez čísel a gambling/adult domén, predvolene „Premium candidates“ alebo „Mixed“. *(agent, 1–2 h)*
5. **Schema pre každú stránku:** `WebPage` + `BreadcrumbList` všade, `FAQPage` na `/how-it-works`, `WebApplication` len na nástrojoch, doplnená `Organization`. *(agent, 1–2 h)*

## Stredná priorita (do mesiaca)
6. **TLD vstupné stránky** `/expired-domains/{tld}` (21×): zoznam vykreslený na serveri, unikátny popis procesu registra, FAQ a `Dataset`. *(agent, 1–2 dni)*
7. **`/recently-expired`** ako skutočná URL (dnes `/#recent`). *(agent, 2–3 h)*
8. **H1 a titulky:** opisné H1 na about, sources, contact a privacy, skrátené titulky nad 60 znakov a popis `/sources`. *(agent, 30 min)*
9. **Rozšíriť `/check-domain`** o vysvetlenie stavov RDAP a FAQ. *(agent, 2 h)*
10. **`/about`:** kto projekt robí, skúsenosti a odkazy na profily. *(ty + agent)*
11. **Kontextové odkazy** medzi `/how-it-works`, `/sources`, `/check-domain` a TLD stránkami. *(agent)*
12. **Launch a zmienky:** Product Hunt, Indie Hackers, NamePros, DNForum, r/Domains, r/SideProject a slovenské a české komunity. *(robíš ty, priebežne)*

## Nízka priorita (backlog)
13. Edge cache pre statické podstránky (`s-maxage`) na nižšie TTFB.
14. Nepredťahovať `/api/domains` na podstránkach (chyby 403 v konzole).
15. Odstrániť duplicitnú hlavičku `X-Content-Type-Options`.
16. Medzera v H1 pri `<br>`.
17. Zjednotiť formát titulkov (`|`) a komunikáciu Premium („SOON“ vs. ponuka).
18. `/glossary` s `DefinedTermSet`.
19. Diagram životného cyklu domény (obrázok + alt) a vlastné OG obrázky.
20. `Offer` schema na `/premium` po spustení.

## Rast obsahu (mesiac 2+)
- Týždenný archív „Notable drops“ (`/drops/2026-w45`), recyklovaný newsletter.
- Návody pre jednotlivé registre: „How .sk domains are released“, „.cz release process“, „.it droptime explained“. Na tieto témy konkurencia nemá obsah.
- Porovnanie „ScopeFlux vs ExpiredDomains.net“ a podobné stránky (skill `/seo-competitor-pages`).

## Monitoring
- Search Console: indexácia nových TLD stránok, dopyty „expired {tld} domains“.
- Bing Webmaster: index (zdroj pre ChatGPT search a Copilot).
- Zopakovať audit o 2 až 3 mesiace: `/seo-audit https://scopeflux.io`.
