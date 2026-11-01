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
