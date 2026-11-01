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
