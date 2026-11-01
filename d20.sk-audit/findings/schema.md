## Schema a štruktúrované dáta (85)

**Čo funguje**
- JSON-LD na všetkých 30 stránkach, bez chýb pri parsovaní.
- `BreadcrumbList` na všetkých podstránkach.
- `WebApplication` s `applicationCategory: GameApplication` a `offers` s cenou 0 na nástrojoch.
- `DefinedTermSet` s `DefinedTerm` a URL na kotvy v slovníku, čo je výborné pre AI citácie.
- `WebSite` na homepage, `inLanguage` všade.

**Nálezy**

| Závažnosť | Nález | Odporúčanie |
|---|---|---|
| Stredná | Chýba entita vydavateľa so `sameAs`. `publisher` je len `Person` s menom, bez URL a profilov. | Pridať `Person` (alebo `Organization`) s `@id`, `url` na stránku „O projekte“ a `sameAs` (Discord, Instagram, GitHub…), potom na ňu odkazovať z `WebSite.publisher`. |
| Nízka | `WebApplication.name` obsahuje príponu „ \| d20.sk“ (skopírovaný titulok). | Použiť čistý názov, napr. „Generátor NPC do DnD“. |
| Nízka | Návody a referenčné stránky nemajú `datePublished` ani `dateModified`. | Doplniť do `WebPage` (alebo použiť `Article` s `author`). |
| Info | FAQ a HowTo rich results Google pre bežné weby už nezobrazuje. | `FAQPage` pridať len ak bude FAQ obsah na stránke. Pre rich results to nerob, pomáha to iba AI vyhľadávačom. |
