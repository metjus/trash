# SEO audit: scopeflux.io

**Dátum:** 1. 11. 2026 · **Nástroj:** claude-seo v2.5.0 (metodika seo-audit) · **Rozsah:** 8 verejných URL (celá sitemapa) + renderovanie hlavnej aplikácie

## Zhrnutie

**SEO Health Score: 75 / 100**

| Kategória | Váha | Skóre |
|---|---|---|
| Technické SEO | 22 % | 85 |
| Kvalita obsahu | 23 % | 62 |
| On-page SEO | 20 % | 75 |
| Schema / štruktúrované dáta | 10 % | 65 |
| Výkon (CWV) | 10 % | 95 |
| Pripravenosť na AI vyhľadávanie | 10 % | 75 |
| Obrázky | 5 % | 70 |

**Typ webu:** SaaS / dátový nástroj (freemium). Zoznam expirujúcich domén pre 21 domén najvyššej úrovne (TLD), kontrola expirácie a pripravované API. Web je v angličtine a cieli globálne.

scopeflux.io má výbornú technickú a bezpečnostnú výbavu:
- kompletné bezpečnostné hlavičky vrátane CSP, Brotli, nemenné (immutable) statické súbory
- `llms.txt` a `security.txt`
- rýchle načítanie, LCP 0,6–1,3 s
- poctivý, citovaný obsah o tom, ako expirácia domén funguje

Hlavné brzdy rastu:

1. **Web má len 8 indexovateľných URL** v silne konkurenčnej oblasti (ExpiredDomains.net, Instant Domain Search, CatchDoms, WhoisFreaks). Chýbajú vstupné stránky pre jednotlivé TLD („expired .io domains“, „expiring .sk domains“…) a samostatná URL pre „Recently expired“ (teraz `/#recent`).
2. **Hlavný obsah nie je v HTML zo servera.** Server pošle prázdny stav („0 results“, „Loading the current list…“) a 456 kB dát v inline JSON. Google zoznam po vykreslení uvidí, to som overil aj so zablokovaným `/api/`. Crawlery bez JavaScriptu však vidia prázdny zoznam. Patria sem GPTBot, ClaudeBot, PerplexityBot a čiastočne Bing.
3. **`www.scopeflux.io` nefunguje** (DNS/proxy vracia chybu). Kto napíše www alebo naň odkáže, dostane chybu.
4. **Rovnaká schéma na všetkých stránkach.** Každá stránka, vrátane Privacy, má ten istý `@graph` (`WebSite` + `Organization` + `WebApplication`). Chýbajú `WebPage`, `BreadcrumbList`, `FAQPage` a `Dataset`.
5. **Prvý dojem zo zoznamu:** pri „Soonest first“ sú navrchu čísla a spam/gambling domény (`0-ad.com`, `00-adultlist.com`, `0055bet-pg.com`). Kvalitné mená ako `aibx.io` sú až na konci prvej strany.

**Top 5 rýchlych výhier**
1. Nastaviť `www.scopeflux.io` → 301 na `https://scopeflux.io/` (DNS záznam + presmerovanie v Cloudflare).
2. Predvolené zoradenie zmeniť na „Premium candidates“ alebo „Mixed extensions“ a spam/IDN-číselné mená odfiltrovať z prvej strany.
3. Vykresliť na serveri prvých ~50 riadkov zoznamu do HTML namiesto „Loading…“.
4. Schému robiť zvlášť pre každú stránku: `WebPage` + `BreadcrumbList` všade, `FAQPage` na `/how-it-works`, `WebApplication` len na nástrojoch.
5. Skrátiť titulky nad 60 znakov (`/how-it-works` 71, `/check-domain` 65) a popis `/sources` (215 znakov).

> **Obmedzenia auditu:** Nie sú pripojené Google Search Console, GA4, CrUX, Moz ani DataForSEO, takže chýbajú reálne dáta o indexácii, pozíciách, návštevnosti a spätných odkazoch. Rýchlosť som meral laboratórne v Chromiu cez sieťový proxy. Chybu `www` som zistil cez proxy (502 pri CONNECT) a treba ju overiť v DNS. Interné skripty claude-seo si overujú DNS samé, preto som dáta zbieral curl-om a Chromiom a vyhodnotil ich podľa metodiky skillu.

---

## Technické SEO (85)

**Čo funguje**
- robots.txt je čistý: blokuje `/api/`, `/account/` a `/status` a odkazuje na sitemapu aj `llms.txt`.
- Sitemapa: 8 URL, všetky 200 a s `lastmod`. Canonical je self-referencing, URL s `?utm_` majú canonical na čistú adresu.
- Lomka na konci → 301 na verziu bez lomky. Stránka 404 vracia skutočný stav 404 a má `noindex, nofollow`.
- Bezpečnosť je vzorová: HSTS (2 roky), CSP, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `security.txt`.
- Brotli na HTML, gzip na súboroch. Súbory s hashom v názve majú `max-age=31536000, immutable`. Cloudflare, HTTP/2 aj HTTP/3.
- Meta robots `index, follow, max-image-preview:large, max-snippet:-1` na všetkých verejných stránkach.

**Nálezy**

| Závažnosť | Nález | Odporúčanie |
|---|---|---|
| Vysoká | Na homepage server pošle prázdny stav zoznamu („0 results“, `<h3>Loading the current list…</h3>`) a dáta (~456 kB JSON) sú v inline `<script>`. Crawlery bez JS vidia prázdnu stránku hlavného produktu. | Server-side vykresliť prvých 50 až 100 riadkov tabuľky do HTML. JS ich iba hydratuje. |
| Stredná | `www.scopeflux.io` nefunguje (502 pri CONNECT, pravdepodobne chýba DNS záznam). | Pridať DNS záznam `www` (proxied) a pravidlo v Cloudflare: 301 `www` → apex so zachovaním cesty. |
| Stredná | HTML homepage má 487 kB, z toho 456 kB tvorí inline JSON s celým zoznamom (630 záznamov). Po Brotli je to ~138 kB, ale parsovanie a hydratácia spomaľujú slabšie mobily. | Vložiť len prvú stranu (100 záznamov) a ďalšie strany doťahovať z API. Alebo dáta zmenšiť (skratky kľúčov, bez opakovaných `sourceUrl`). |
| Nízka | Podstránky (`/check-domain`, `/how-it-works`, `/premium`, `/sources`) volajú na pozadí `/api/domains?period=7`, server vracia 403 a v konzole je chyba. | Nepredťahovať zoznam na stránkach, ktoré ho nezobrazujú, alebo poslať guard token aj tam. |
| Nízka | HTML má `cache-control: private, no-store` a `cf-cache-status: DYNAMIC`. TTFB 0,4–0,9 s. | Statické podstránky (how-it-works, sources, about, privacy) cachovať na edge (`s-maxage`). |
| Nízka | Hlavička `X-Content-Type-Options` sa posiela dvakrát. | Odstrániť duplicitu (aplikácia aj Cloudflare). |
| Info | `/index.html` a veľké písmená vracajú 404. | V poriadku. |

## Kvalita obsahu (62)

**Čo funguje**
- `/how-it-works` (~1 000 slov) a `/sources` (~800 slov) sú nadpriemerné. Vysvetľujú grace period, redemption, pending delete a rozdiely medzi TLD a citujú primárne zdroje (ICANN, CZ.NIC, SK-NIC, Registro .it, auDA, Verisign). Silný signál E-E-A-T.
- Poctivé vymedzenie („not a registrar“, „a date is a forecast“) buduje dôveru.
- `/contact` uvádza prevádzkovateľa: meno, adresu a IČO.
- Jedinečná výhoda: pokrytie .sk, .cz, .it a .au, ktoré bežné nástroje nemajú. Pri vyhľadávaní .sk drop listov som nenašiel konkurenciu.

**Nálezy**

| Závažnosť | Nález | Odporúčanie |
|---|---|---|
| Vysoká | Len 8 URL, žiadne vstupné stránky pre jednotlivé TLD. Dopyty ako „expired .io domains“, „expiring .co.uk domains“ či „.sk domény na uvoľnenie“ nemajú kam pristáť. | Vytvoriť `/expired-domains/{tld}` pre 21 TLD: zoznam vykreslený na serveri, unikátny popis procesu daného registra, zdroj, časovanie, FAQ. |
| Vysoká | „Recently expired“ je len `/#recent`, „Watchlist“ `/#watch`. Hash nie je samostatná indexovateľná URL. | `/recently-expired` ako skutočná stránka (SSR, canonical, v sitemape). Watchlist nechať neindexovaný. |
| Stredná | Prvá strana zoznamu („Soonest first“) začína číselnými a spam/gambling doménami. Pôsobí to nekvalitne na ľudí aj pri hodnotení kvality. | Predvolene radiť podľa kvality (Premium potential) alebo „Mixed“ a filtrovať zjavný spam (slová bet, slot, adult, casino, náhodné reťazce). |
| Stredná | `/check-domain` má ~300 slov vrátane šablóny, takmer len formulár. | Pridať 300–500 slov: čo znamenajú stavy RDAP (clientHold, redemptionPeriod, pendingDelete), ako čítať dátum expirácie, FAQ. |
| Stredná | `/about` nemenuje ľudí za projektom. Prevádzkovateľ je len na `/contact`. | Na `/about` pridať sekciu „Who builds ScopeFlux“ s menom, skúsenosťami s doménami a odkazmi (LinkedIn, X, GitHub). |
| Nízka | Chýba glosár pojmov (drop catching, backorder, redemption, RGP, pending delete…). | `/glossary` s `DefinedTermSet`. Je to dobrý cieľ pre AI citácie aj dlhý chvost dopytov. |

## On-page SEO (75)

**Čo funguje**
- Titulky sú unikátne a cielia na hlavné dopyty („Expired Domains List“, „Domain Expiration Date Checker“, „Expired Domains API“).
- Meta popisy sú unikátne, väčšinou 135–161 znakov.
- Jeden H1 na stránku. Open Graph a Twitter Card sú kompletné.
- `/how-it-works` a `/sources` majú logickú hierarchiu H2/H3.

**Nálezy**

| Závažnosť | Nález | Odporúčanie |
|---|---|---|
| Stredná | H1 na `/about` („A good name. A new beginning.“), `/sources` („Data you can understand.“), `/contact` a `/privacy` sú slogany bez kľúčových slov. | Prvý riadok nechať ako slogan, ale do H1 dať opisný text, napr. „About ScopeFlux, a free expired domain finder“, „Expired domain data sources“. |
| Stredná | Interné odkazy sú len navigácia a pätička. Žiadne kontextové odkazy medzi obsahom a nástrojmi (okrem CTA). | Z `/how-it-works` odkazovať na TLD stránky a `/check-domain`. Zo `/sources` na TLD stránky, ktoré daný zdroj pokrýva. |
| Nízka | Titulky dlhšie ako ~60 znakov sa v SERP orežú: `/how-it-works` 71, `/check-domain` 65, `/` 62. | Napr. „Domain Expiry Explained: Redemption & Pending Delete“ alebo „Domain Expiration Checker: When Does It Expire?“. |
| Nízka | Popis `/sources` má 215 znakov. | Skrátiť na ~155. |
| Nízka | Titulky `Contact — ScopeFlux` a `Privacy — ScopeFlux` používajú inú pomlčku a formát ako ostatné (`|`). | Zjednotiť formát. |
| Nízka | V H1 chýba medzera medzi riadkami (`domains.Upcoming`), lebo `<br>` je bez medzery. Niektoré nástroje a snippety ich spoja. | Pridať medzeru pred `<br>` alebo riadky dať do `<span>` s medzerou. |
| Nízka | Breadcrumb „Workspace / Expiring soon“ je aplikačný, nie navigačný. | Pre obsahové stránky použiť „Home / How it works“ a prepojiť ho s `BreadcrumbList`. |

## Schema a štruktúrované dáta (65)

**Čo funguje**
- Validný JSON-LD s `@id` prepojeniami (`WebSite.publisher` → `#organization`).
- `Organization` má `logo` a `email`. `WebApplication` má `isAccessibleForFree` a `offers`.

**Nálezy**

| Závažnosť | Nález | Odporúčanie |
|---|---|---|
| Stredná | Všetkých 8 stránok má **identický** `@graph`, aj Privacy a Contact majú `WebApplication`. | Spoločné nechať `WebSite` + `Organization` (s `@id`) a pridať pre každú stránku `WebPage` (`name`, `url`, `description`, `isPartOf`) a `BreadcrumbList`. `WebApplication` dať len na `/` a `/check-domain`. |
| Stredná | `/how-it-works` má viditeľnú sekciu „Common questions“ (5 otázok) bez `FAQPage`. | Pridať `FAQPage` s rovnakými otázkami. Google FAQ rich results pre bežné weby obmedzil, ale AI vyhľadávače štruktúru využijú. |
| Stredná | `Organization` nemá `founder`, `address`, `sameAs` ani `vatID`/`identifier`, hoci údaje sú na `/contact`. | Doplniť `founder` (`Person`), `address` (PostalAddress SK) a `identifier` (IČO). `sameAs` doplniť po vytvorení profilov. |
| Nízka | Zoznam domén je dátová sada bez `Dataset` schémy. | `Dataset` na `/` a TLD stránkach (`name`, `description`, `creator`, `temporalCoverage`, `isAccessibleForFree`, `license`). Môže sa zobraziť v Google Dataset Search. |
| Nízka | `/premium` nemá `Offer`/`Product` pre plány. | Doplniť po spustení Premium (cena, mena, `availability: PreOrder` alebo `InStock`). |

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

## Vizuál a mobil

Screenshoty sú v priečinku `screenshots/`.

- Moderný tmavý dizajn. Na mobile je H1, úvod a vyhľadávanie hneď na prvej obrazovke. Žiadne horizontálne pretečenie.
- **Nízka:** Na desktope je veľa malých dotykových cieľov (< 24 px) v riadkoch zoznamu a v bočnom paneli. Na mobile je to OK.
- **Nízka:** Bočný panel ukazuje „Premium SOON“, ale `/premium` sa tvári ako hotová ponuka API („Expired domains API. CSV export included.“). Zjednotiť komunikáciu.

## Obrázky (70)

- Na stránkach nie sú obsahové obrázky (ikony sú inline SVG). Hero „radar“ je CSS/SVG, takže netreba alt texty.
- OG obrázok je jeden pre všetky stránky (`og-image.png`, 175 kB PNG). Vlastné OG obrázky pre TLD stránky a `/how-it-works` (diagram životného cyklu domény) zvýšia CTR pri zdieľaní.
- **Príležitosť:** diagram „životný cyklus domény“ (expired → grace → redemption → pending delete → release) ako obrázok s alt textom. Dobre sa umiestňuje v Google Obrázkoch a často sa naň odkazuje.

## Pripravenosť na AI vyhľadávanie (75)

**Čo funguje**
- **`llms.txt` je vzorový**: popis produktu, hlavné stránky, zdroje dát a obmedzenia.
- robots.txt neblokuje AI crawlery. Obsah `/how-it-works` a `/sources` je v serverovom HTML a dobre citovateľný (krátke definície, FAQ).
- Citované primárne zdroje zvyšujú dôveryhodnosť.

**Nálezy**

| Závažnosť | Nález | Odporúčanie |
|---|---|---|
| Vysoká | AI crawlery nespúšťajú JS, takže na homepage vidia „0 results / Loading…“. | SSR prvých riadkov zoznamu (rovnaká oprava ako v technickom SEO). |
| Vysoká | Značka nemá žiadne zmienky mimo webu. Vyhľadávanie „scopeflux“ nenašlo nič. | Spustiť web na Product Hunt, Indie Hackers, DNForum, NamePros, r/Domains, r/SideProject a v slovenských a českých komunitách (.sk/.cz pokrytie je unikátne). Napísať hosťovský článok do domain blogov (DomainNameWire, TheDomains). |
| Nízka | Chýba glosár a pravidelný obsah („notable drops this week“). | Newsletter „Notable drops, every Monday“ publikovať aj ako webový archív (`/drops/2026-w45`). Vzniká čerstvý, citovateľný obsah. |

## Lokálne SEO, e-commerce, spätné odkazy

- **Lokálne / mapy:** nevzťahuje sa.
- **E-commerce:** nevzťahuje sa (Premium je predplatné, zatiaľ „coming soon“).
- **Spätné odkazy:** Moz, Bing ani DataForSEO nie sú pripojené. Podľa vyhľadávania zatiaľ bez viditeľných odkazov. Sitewide odkaz na `qrko.net` (vlastný projekt) je v poriadku.
- **Drift baseline:** neexistuje (prvý audit).
