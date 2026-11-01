## On-page SEO (82)

**Čo funguje**
- Titulky majú 23–60 znakov, sú unikátne a obsahujú kľúčové slovo aj značku.
- Meta popisy sú unikátne a väčšinou majú 111–169 znakov. Výnimkou sú stránky o súkromí, ktoré majú 69 a 76 znakov.
- Každá stránka má práve jeden H1, ktorý zodpovedá téme.
- Open Graph a Twitter Card sú kompletné na všetkých stránkach (vrátane rozmerov a alt textu).
- Zrozumiteľné slovenské URL (`/generator-krcmy/`, `/harok-postavy/`).
- Každá stránka má odkazy zo všetkých ostatných (navigácia a pätička), takže žiadna nie je osirelá.

**Nálezy**

| Závažnosť | Nález | Odporúčanie |
|---|---|---|
| Stredná | Na každej stránke sú 3 H2 zo šablóny: „List do Veže osudu“, „List je zapečatený!“ a „Čo by si tu chcel?“. Na `/kocky/` sú to jediné H2. | Zmeniť ich na `<p class="…">` alebo `<div role="heading">` mimo obsahovej hierarchie. |
| Stredná | Prázdne nadpisy, ktoré dopĺňa JS: `<h3>` na homepage (karta hrdinu) a `<h2>` na `/tvorba-postavy/`. | Dať do nich predvolený text alebo nadpis vložiť až s obsahom. |
| Nízka | `/navody/` skáče z H1 rovno na H3 (5 krokov) a H2 („Knižnica“) prichádza až potom. | Kroky zabaliť pod H2 „Ako začať v 5 krokoch“. |
| Nízka | Málo kontextových odkazov z nástrojov. `/generator-npc/` odkazuje v obsahu len na breadcrumb. | Z generátorov odkazovať na súvisiace stránky (NPC → krčma → tracker súboja, kocky → hárok postavy). |
| Nízka | Krátke meta popisy na `/ochrana-osobnych-udajov/` (76) a `/en/privacy/` (69). | Nevadí, sú to stránky s nízkou prioritou. |
