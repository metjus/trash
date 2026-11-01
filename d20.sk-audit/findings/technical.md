## Technické SEO (90)

**Čo funguje**
- robots.txt je v poriadku: `Allow: /` a blokuje len interné priečinky (`/php/`, `/inc/`, `/partials/`, `/pages/`) a odkazuje na sitemapu.
- Sitemapa: 30 URL, všetky vracajú 200, všetky majú `lastmod` a hreflang a žiadna stránka mimo sitemapy sa nenašla.
- Canonical je self-referencing na všetkých stránkach. URL s parametrami (`?utm_source=…`) majú canonical na čistú adresu.
- Presmerovania sú konzistentné: `www` → bez www (301), chýbajúca lomka → s lomkou (301), `/index.html` → `/` (301).
- Vlastná stránka 404 vracia skutočný stav 404 a má `noindex`.
- HTTPS s HSTS (2 roky, includeSubDomains), `X-Content-Type-Options`, HTTP/2 aj HTTP/3.
- Statické súbory majú verziu v URL a `max-age` 1 rok, HTML je komprimované gzipom.
- `lang` atribút sedí s jazykom stránky (sk/en). Hreflang je obojsmerný a má `x-default`.

**Nálezy**

| Závažnosť | Nález | Odporúčanie |
|---|---|---|
| Stredná | Odkazy v „Mape kráľovstva“ na homepage vkladá až JavaScript: v surovom HTML sú 4 odkazy v `<main>`, po vykreslení 14. | Google JS vykreslí, ale je bezpečnejšie dať odkazy priamo do HTML. Navigácia ich už obsahuje, takže dopad je malý. |
| Nízka | Chýbajú bezpečnostné hlavičky `Content-Security-Policy`, `Referrer-Policy`, `Permissions-Policy` a `X-Frame-Options` (alebo `frame-ancestors`). | Doplniť ich v nginx. Na pozície nemajú priamy vplyv, sú to signály dôvery a ochrany. |
| Nízka | Kompresia je len gzip, nie Brotli. | Zapnúť Brotli (`brotli on;`), ušetrí ~15–20 % na HTML/CSS/JS. |
| Nízka | `/NAVODY/` (veľké písmená) vracia 404. | Je to v poriadku, len to netreba nikde odkazovať. |
| Info | `/llms.txt` a `/.well-known/security.txt` neexistujú. | Oba sú voliteľné, pozri sekciu o AI vyhľadávaní. |
