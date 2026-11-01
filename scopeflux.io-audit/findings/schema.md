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
