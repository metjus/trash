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
