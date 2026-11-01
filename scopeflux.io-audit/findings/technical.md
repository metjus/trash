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
