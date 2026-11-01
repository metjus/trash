# Akčný plán: d20.sk

Aktuálne skóre **80/100**. Body 1 až 8 by ho mali posunúť na ~90.

## Kritické
Žiadne. Nič neblokuje indexáciu a nehrozí penalizácia.

## Vysoká priorita (do týždňa)
1. **Google Search Console a Bing Webmaster Tools:** overiť doménu, odoslať `sitemap.xml`, skontrolovať indexáciu všetkých 30 URL a zapnúť IndexNow. *(30 min)*
2. **Rozšíriť `/kocky/` a `/en/dice-roller/`:** 300–500 slov pod nástrojom (kocky v DnD, výhoda/nevýhoda, zápis 2d6+3) a FAQ. *(2 h)*
3. **Rozšíriť `/tvorba-postavy/` a `/en/character-creator/`:** postup tvorby postavy v 6 krokoch, ako rozdeliť vlastnosti a odkazy na povolania, rasy a hárok. *(2–3 h)*
4. **Stránka „O projekte“** (`/o-projekte/`, `/en/about/`): kto web robí, prečo a skúsenosti s DnD. Odkaz z pätičky, `Person` + `sameAs` v schéme. *(1–2 h)*
5. **Zmienky o značke:** predstaviť web na Discorde D&D Slovakia, v slovenských a českých RPG skupinách a na Reddite. Ponúknuť nástroje herným obchodom a klubom. *(priebežne)*

## Stredná priorita (do mesiaca)
6. **Nadpisy v šablóne:** „List do Veže osudu“, „List je zapečatený!“ a „Čo by si tu chcel?“ z `<h2>` zmeniť na ne-nadpisové prvky. Odstrániť prázdne `<h3>`/`<h2>`. Na `/navody/` doplniť H2 nad 5 krokov. *(30 min)*
7. **Mobil:** H1 a úvod presunúť nad obrázok kocky alebo obrázok zmenšiť na ~45 % výšky. Znížiť výšku cookie lišty. *(1 h)*
8. **`/navody/`** rozšíriť na hlavný návod (1 000+ slov) s FAQ blokom (krátke odpovede pre AI). *(3–4 h)*
9. **Dátumy:** zobraziť „Aktualizované: …“ na návodoch a doplniť `dateModified` do schémy. *(30 min)*
10. **Kontextové odkazy** medzi nástrojmi (NPC ↔ krčma ↔ poklad ↔ tracker, kocky ↔ hárok). *(1 h)*
11. **Odkazy „Mapy kráľovstva“** na homepage dať priamo do HTML namiesto vkladania cez JS. *(30 min)*

## Nízka priorita (backlog)
12. Bezpečnostné hlavičky v nginx: CSP, Referrer-Policy, Permissions-Policy, frame-ancestors.
13. Brotli kompresia.
14. `WebApplication.name` bez prípony „| d20.sk“.
15. Vlastné OG obrázky pre jednotlivé nástroje.
16. Ilustrácie povolaní a rás s alt textom (Google Obrázky).
17. `llms.txt` so zoznamom hlavných stránok.
18. 3D kocky načítať až po interakcii (TBT 160 ms na desktope).
19. Väčšie dotykové plochy v pätičke a breadcrumb (min. 24×24 px).

## Rast obsahu (mesiac 2+)
- Samostatné stránky pre každé povolanie a rasu (`/povolania/bojovnik/` …), 24 nových URL v SK aj EN.
- „Ako byť Dungeon Master“, „Prvé sedenie krok za krokom“, slovník kúziel.
- Jednorazové dobrodružstvo na stiahnutie (PDF) ako magnet na odkazy.
- Prehľad slovenských DnD komunít a obchodov (oplatí sa za ním aj výmena odkazov).

## Monitoring
- Mesačne Search Console: indexácia, dopyty, CTR.
- Po zmenách nástrojov znova merať Core Web Vitals.
- O 2–3 mesiace zopakovať audit (`/seo-audit https://d20.sk`).
