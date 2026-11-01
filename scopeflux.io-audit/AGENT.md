# Úloha pre agenta: SEO opravy na scopeflux.io

Tento súbor je zadanie pre AI agenta (napr. Claude Code), ktorý pracuje v repozitári so zdrojovým kódom **scopeflux.io**. Vychádza z auditu z 1. 11. 2026 (`FULL-AUDIT-REPORT.md`, skóre 75/100). Cieľ je dostať sa na ~88 a vytvoriť základ pre rast cez TLD stránky.

## Kontext webu

- Web aplikácia v angličtine za Cloudflare. Server predrenderuje HTML stránky (`"prerendered": true` v inline JSON) a JS bundle (`/assets/app.<hash>.js`) ju hydratuje.
- Homepage vkladá dáta zoznamu ako inline JSON (`{"url":"/api/domains?period=7","data":{"records":[…]}}`, ~456 kB) spolu s guard tokenom (`"guard": "…"`). API `/api/domains` bez platného guardu vracia 403 (ochrana proti scrapingu).
- Verejné stránky: `/`, `/check-domain`, `/how-it-works`, `/sources`, `/about`, `/premium`, `/contact`, `/privacy`. Aplikačné pohľady `/#recent` a `/#watch`.
- robots.txt blokuje `/api/`, `/account/`, `/status`. Existujú `llms.txt`, `security.txt` a `sitemap.xml`.
- Zdroje dát: NameBio (Verisign), SnapNames, Dynadot, Registro .it, auDA, CZ.NIC, Backorder.sk a RDAP.
- Prísna CSP: `script-src 'self' https://static.cloudflareinsights.com` (inline JS nie je povolené, inline `application/json` a `application/ld+json` áno).

Najprv si prezri štruktúru repozitára: kde sa generuje HTML (SSR/prerender), kde sú šablóny stránok, JSON-LD, sitemapa a `llms.txt`, a ako sa načítavajú a filtrujú dáta zoznamu. Nič nepredpokladaj, over si to v kóde.

## Pravidlá

1. **Nemeň existujúce URL** ani canonicaly. Nové stránky pridaj do sitemapy aj `llms.txt`.
2. **Nerozbi to, čo funguje:** bezpečnostné hlavičky a CSP, LCP < 1,5 s, CLS 0, jeden H1 na stránku, `noindex` na 404.
3. **Anti-scraping ostáva.** SSR zobrazí len to, čo je aj tak viditeľné na prvej strane (max. 100 riadkov). Neotváraj API bez guardu a nedávaj do HTML celý dataset.
4. **Žiadny inline JS** (kvôli CSP). Dáta len ako `type="application/json"`.
5. **Obsah o registroch píš len z overiteľných zdrojov**, ktoré web už cituje (ICANN, CZ.NIC, SK-NIC, nic.it, auDA, Verisign). Ak si fakt nevieš overiť, nevymýšľaj ho a označ `TODO(majiteľ): overiť`. Zachovaj poctivý tón („a date is a forecast“, „not a registrar“).
6. **Nevymýšľaj údaje o majiteľovi** (profily, skúsenosti). Kde chýbajú, nechaj `TODO(majiteľ): …` a uveď ich v súhrne.
7. **Neindexuj stránky jednotlivých domén.** Hrozí index bloat a tenký obsah. Indexovateľné sú len hub stránky (TLD, recently expired).
8. Po každej úlohe spusti kontrolu z časti **Overenie**.

## Úlohy

Rob ich v tomto poradí. Každá má akceptačné kritériá.

### 1. SSR zoznamu na homepage (vysoká)

Dnes server pošle `0 results` a `<h3>Loading the current list…</h3>` a zoznam vykreslí až JS. Crawlery bez JS (GPTBot, ClaudeBot, PerplexityBot, čiastočne Bing) vidia prázdny produkt.

- Pri prerenderingu vykresli do HTML hlavičku výsledkov so skutočným počtom („630 results · Within 7 days · All extensions“) a prvých 50 až 100 riadkov tabuľky s rovnakým markupom, aký vytvára klient (doména, zdroj, dátum, stav).
- Hydratácia musí riadky prevziať bez blikania (žiadne prekreslenie, CLS 0).
- Inline JSON zmenši len na dáta prvej strany. Ďalšie strany a filtre doťahuj cez existujúce API s guardom.

**Hotovo, keď:** `curl -s https://<staging>/ | grep -c 'Loading the current list'` vráti 0, HTML obsahuje ≥ 50 názvov domén, veľkosť HTML homepage je < 150 kB (nekomprimovaná) a filtre, stránkovanie a CSV fungujú ako predtým.

### 2. Predvolené zoradenie a filter spamu (vysoká)

Prvá strana pri „Soonest first“ začína mená ako `0-ad.com`, `00-adultlist.com`, `0055bet-pg.com`.

- Predvolené zoradenie zmeň na kvalitu (existujúca heuristika „Premium potential“), alebo na „Mixed extensions“ so zoradením podľa kvality v rámci dňa. Zostáva deterministické (rovnaké poradie pre SSR aj klienta).
- Pridaj filter „hide likely spam“, predvolene zapnutý: mená s výrazmi ako `bet|slot|casino|adult|porn|xxx|loan|viagra`, s viac ako 4 číslicami a náhodné reťazce (nízky podiel samohlások). Pravidlá daj do jednej konfigurácie a priznaj ich v UI („How we select names“).

**Hotovo, keď:** prvých 20 riadkov predvoleného zobrazenia neobsahuje mená zodpovedajúce spam pravidlám a používateľ si filter vie vypnúť.

### 3. Štruktúrované dáta pre každú stránku (vysoká)

Dnes má všetkých 8 stránok identický `@graph` (`WebSite` + `Organization` + `WebApplication`).

- **Spoločné na všetkých stránkach:** `WebSite` (`@id: …/#website`) a `Organization` (`@id: …/#organization`). `Organization` doplň o údaje, ktoré sú už na `/contact`:

```json
{"@type": "Organization", "@id": "https://scopeflux.io/#organization", "name": "ScopeFlux",
 "url": "https://scopeflux.io/", "logo": "https://scopeflux.io/icon-512.png", "email": "hello@scopeflux.io",
 "founder": {"@type": "Person", "name": "Matúš Šturdík"},
 "address": {"@type": "PostalAddress", "streetAddress": "Nová 407", "addressLocality": "Veľká Mača", "addressCountry": "SK"},
 "identifier": {"@type": "PropertyValue", "propertyID": "IČO", "value": "51628163"}}
```

  `sameAs` pridaj až keď majiteľ dodá profily (`TODO(majiteľ)`).
- **Pre každú stránku:** `WebPage` (`@id: <url>#webpage`, `url`, `name`, `description`, `isPartOf: #website`, `inLanguage: en`) a `BreadcrumbList` (Home › Názov stránky). Na `/about` použi `AboutPage`, na `/contact` `ContactPage`.
- **`WebApplication`** len na `/` a `/check-domain`, každá s vlastným `name` a `url`.
- **`FAQPage`** na `/how-it-works` s presne tými 5 otázkami a odpoveďami, ktoré sú viditeľné v sekcii „Common questions“.
- **`Dataset`** na `/` (neskôr aj na TLD stránkach): `name`, `description`, `creator: #organization`, `isAccessibleForFree: true`, `temporalCoverage` (dnes až +N dní), `variableMeasured` (domain, expected release date, source), `license` (podľa podmienok, ak nie sú, `TODO(majiteľ)`).

**Hotovo, keď:** každá stránka má vlastný `WebPage` + `BreadcrumbList`, žiadna obsahová stránka nemá `WebApplication`, JSON-LD sa dá bez chyby sparsovať a prejde v Rich Results Teste a na validator.schema.org.

### 4. H1, titulky a popisy (stredná)

| Stránka | Zmena |
|---|---|
| `/about` | H1 → „About ScopeFlux: a free expired domain finder“ (slogan môže ostať ako kicker alebo podnadpis) |
| `/sources` | H1 → „Expired domain data sources“ |
| `/contact` | H1 → „Contact ScopeFlux“, titulok → „Contact ScopeFlux \| Expired Domain Finder“ |
| `/privacy` | H1 → „Privacy policy“, titulok → „Privacy Policy \| ScopeFlux“ |
| `/how-it-works` | titulok (71 zn.) → „Domain Expiry Explained: Redemption & Pending Delete“ (≤ 60 zn. bez značky je OK) |
| `/check-domain` | titulok (65 zn.) → „Domain Expiration Checker: When Does It Expire?“ |
| `/sources` | meta popis (215 zn.) skrátiť na ≤ 160 znakov |

- Zjednoť oddeľovač značky na ` | ScopeFlux`.
- V H1 so zalomením pridaj medzeru pred `<br>`, aby sa text nespájal (`domains. Upcoming`).

**Hotovo, keď:** všetky titulky majú ≤ 65 znakov, popisy 120–160 znakov a H1 opisuje tému stránky.

### 5. TLD vstupné stránky (stredná, najväčší rastový potenciál)

Vytvor hub `/expired-domains` a 21 stránok `/expired-domains/{tld}` pre: com, net, org, io, app, xyz, info, me, biz, us, pro, cc, tv, co-uk, uk, org-uk, com-au, au, it, sk, cz. Slug pre viacúrovňové TLD píš s pomlčkou.

Každá stránka obsahuje:
- **Titulok:** „Expired .{tld} Domains: Expiring & Dropping Soon | ScopeFlux“ (≤ 65 zn.). **H1:** „Expired and expiring .{tld} domains“.
- **Zoznam vykreslený na serveri** (top 50–100 pre daný TLD) s rovnakou hydratáciou a filtrami ako homepage (predvyplnený filter TLD).
- **Unikátny text 300–600 slov:** kto je register, ako prebieha expirácia a uvoľnenie (grace, redemption, pending delete, aukcia), kedy a ako sa uvoľňuje (napr. .it 09:00/16:00 talianskeho času, .au purge UTC, .cz bez aukčných mien), odkiaľ ScopeFlux berie dáta a aké sú obmedzenia. Fakty ber z `/how-it-works`, `/sources` a `llms.txt`, nevymýšľaj.
- **FAQ (3–5 otázok)** + `FAQPage`, `Dataset`, `BreadcrumbList` (Home › Expired domains › .{tld}).
- **Odkazy:** na `/how-it-works`, `/sources#<zdroj>`, `/check-domain` a 3–5 súvisiacich TLD.
- **Prázdny stav:** ak TLD nemá dnes žiadne záznamy, stránka zostane indexovateľná (text, FAQ), ale zobrazí „No .{tld} releases listed in the next 7 days“ a odkaz na recently expired. Nikdy nevracaj 404 len kvôli prázdnemu zoznamu.

Doplň aj:
- hub `/expired-domains` s tabuľkou 21 TLD (počet aktuálnych záznamov, zdroj, odkaz),
- odkazy na TLD stránky z filtrov na homepage (napr. názov TLD → stránka) a z pätičky,
- všetkých 22 URL do `sitemap.xml` (s `lastmod` podľa poslednej aktualizácie dát) a do `llms.txt`.

**Hotovo, keď:** 22 nových URL vracia 200, každá má self-canonical, unikátny titulok, popis a text (žiadne dva texty nie sú šablónové kópie s vymeneným názvom TLD), zoznam je v HTML a stránky sú v sitemape aj `llms.txt`.

### 6. `/recently-expired` ako skutočná stránka (stredná)

- Vytvor `/recently-expired` (SSR, rovnaký zoznam ako pohľad `#recent`), s titulkom „Recently Expired Domains: Dropped in the Last 7 Days | ScopeFlux“, krátkym úvodom (100–200 slov) a `WebPage`, `BreadcrumbList` a `Dataset`.
- Odkaz „Recently expired“ v bočnom paneli smeruj na novú URL. `/#recent` presmeruj klientsky na `/recently-expired`.
- `/#watch` ostáva bez zmeny (osobný obsah, neindexovať).

### 7. Rozšírenie `/check-domain` (stredná)

Pod formulár pridaj 300–500 slov:
- H2 „What the domain statuses mean“: `active`, `clientHold`, `serverHold`, `autoRenewPeriod`, `redemptionPeriod`, `pendingDelete`, `pendingTransfer`, ku každému 1–2 vety podľa RFC 8056/EPP,
- H2 „How to read the expiration date“: vysvetliť, prečo dátum expirácie ≠ dátum uvoľnenia,
- H2 „Common questions“ (3–4) + `FAQPage`,
- odkazy na `/how-it-works` a TLD stránky.

### 8. Kontextové odkazy (stredná)

- `/how-it-works`: pri zmienkach o konkrétnych TLD (.sk, .cz, .it…) odkazuj na ich TLD stránky a v závere na `/check-domain`.
- `/sources`: pri každom zdroji odkazuj na TLD stránky, ktoré pokrýva.
- `/about`: odkaz na `/expired-domains`.

### 9. Technické drobnosti (nízka)

- Na podstránkach, ktoré zoznam nezobrazujú, nevolaj `/api/domains` (dnes 403 a chyba v konzole).
- Odstráň duplicitnú hlavičku `X-Content-Type-Options` (posiela ju aj aplikácia, aj Cloudflare, nechaj jednu).
- Statické podstránky (`/how-it-works`, `/sources`, `/about`, `/privacy`, `/contact`, `/glossary`) cachuj na edge: `Cache-Control: public, max-age=0, s-maxage=3600`. Homepage a stránky so zoznamom nechaj dynamické alebo s krátkym `s-maxage` (napr. 300), ak to guard token dovolí.
- Zjednoť komunikáciu Premium: bočný panel hovorí „SOON“, `/premium` ponúka API ako hotové. H1 na `/premium` doplň napr. o „(coming soon)“, alebo upravuj podľa skutočného stavu.

### 10. Glosár (nízka)

`/glossary` s 15–25 pojmami (expiration, grace period, auto-renew grace, redemption grace period, pending delete, drop, drop catching, backorder, aukcia, RDAP, WHOIS, EPP status, registry, registrar, premium domain…). Každý pojem má kotvu, definíciu na 1–3 vety a odkaz na ďalší obsah. Pridaj `DefinedTermSet` a stránku do sitemapy, `llms.txt` a pätičky.

## Mimo rozsahu agenta (urobí majiteľ)

- DNS záznam `www` a presmerovanie 301 `www` → apex v Cloudflare.
- Overenie v Google Search Console a Bing Webmaster Tools, odoslanie sitemapy.
- Profily značky (`sameAs`), sekcia o tvorcovi na `/about`.
- Launch a zmienky: Product Hunt, Indie Hackers, NamePros, DNForum, r/Domains, r/SideProject, slovenské a české komunity.
- Grafika: diagram životného cyklu domény a OG obrázky pre TLD stránky.

## Overenie

Po zmenách spusti web lokálne alebo na stagingu a over:

```bash
BASE=http://localhost:3000   # uprav podľa projektu
for u in $(curl -s $BASE/sitemap.xml | grep -o '<loc>[^<]*' | sed 's/<loc>//; s#https://scopeflux.io#'$BASE'#'); do
  html=$(curl -s "$u")
  code=$(curl -s -o /dev/null -w '%{http_code}' "$u")
  h1=$(grep -o '<h1' <<<"$html" | wc -l)
  title=$(grep -o '<title>[^<]*' <<<"$html" | sed 's/<title>//')
  loading=$(grep -c 'Loading the current list' <<<"$html")
  ld=$(grep -c 'application/ld+json' <<<"$html")
  echo "$code h1=$h1 loading=$loading ld=$ld len=${#title} $u | $title"
done
```

Očakávané: všade `200 h1=1 loading=0 ld≥1`, dĺžka titulku ≤ 65. Ďalej over:
- JSON-LD každej stránky sa dá sparsovať a nemá duplicitné `@id` s odlišným obsahom. Prejde v [Rich Results Test](https://search.google.com/test/rich-results) / [validator.schema.org](https://validator.schema.org/).
- `curl -s $BASE/ | grep -oE '[a-z0-9-]+\.(com|net|org|io)' | sort -u | wc -l` ≥ 50 (zoznam je v HTML).
- Veľkosť HTML homepage < 150 kB nekomprimovaná.
- Lighthouse (mobil) pre `/`, `/expired-domains/io`, `/check-domain`: LCP < 2,5 s, CLS < 0,1, SEO 100, žiadne chyby v konzole.
- CSP v konzole nehlási porušenia.
- Filtre, stránkovanie, CSV export, watchlist a prihlásenie fungujú ako predtým.

## Výstup

Na konci napíš súhrn:
1. zoznam zmenených a nových súborov podľa úloh,
2. nové URL (pre sitemapu a Search Console),
3. čo sa nepodarilo alebo čo si vynechal a prečo,
4. všetky `TODO(majiteľ)` s presným miestom v kóde,
5. výsledok overovacieho skriptu.
