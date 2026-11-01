# Úloha pre agenta: SEO opravy na d20.sk

Tento súbor je zadanie pre AI agenta (napr. Claude Code), ktorý pracuje v repozitári so zdrojovým kódom webu **d20.sk**. Vychádza z auditu z 1. 11. 2026 (`FULL-AUDIT-REPORT.md`, skóre 80/100). Cieľ je dostať sa na ~90.

## Kontext webu

- Statický/PHP web, nginx, Cloudflare Web Analytics (bez cookies).
- Dva jazyky so zrkadlovou štruktúrou: SK v koreni (`/navody/`), EN pod `/en/` (`/en/guides/`). 15 + 15 stránok.
- Šablóny sú pravdepodobne v `/partials/`, `/inc/`, `/pages/` alebo `/php/` (robots.txt tieto priečinky blokuje). Spoločná hlavička, pätička, formulár „List do Veže osudu“ a cookie lišta sa vkladajú na každú stránku.
- JSON-LD je v `<head>` každej stránky (`@graph`: `BreadcrumbList` + `WebPage`/`WebApplication`/`DefinedTermSet`, na homepage `WebSite`).
- JS je rozdelený po stránkach (`/js/core.js`, `/js/npc.js`, `/js/dice.js` …), statické súbory majú verziu v query stringu (`?v=hash`).

Najprv si prezri štruktúru repozitára a nájdi, kde sa generuje hlavička, pätička, formulár a JSON-LD. Nič nepredpokladaj, over si to v kóde.

## Pravidlá

1. **Nemeň existujúce URL**, canonicaly ani hreflang. Všetky fungujú správne.
2. **Každú zmenu urob v SK aj EN verzii.** Jazyky musia zostať zrkadlové.
3. **Nerozbi to, čo funguje:** jeden H1 na stránku, unikátne titulky a popisy, self-canonical, obojsmerný hreflang, CLS ≈ 0, LCP ~1 s.
4. **Obsah o pravidlách DnD píš len zo SRD 5.1/5.2 (CC BY 4.0)** alebo vlastnými slovami. Nekopíruj text z Player's Handbook ani z iných webov. Neuvádzaj fakty, ktoré si nevieš overiť.
5. **Nevymýšľaj údaje o autorovi** (profily, skúsenosti, mesto). Kde chýbajú, nechaj zreteľný placeholder `TODO(majiteľ): …` a uveď ho v súhrne na konci.
6. Štýl textu: tykanie, jednoduchý jazyk pre začiatočníkov, anglický originál pojmu v zátvorke pri prvom výskyte (ako na `/povolania/`).
7. Po každej úlohe spusti kontrolu z časti **Overenie**.

## Úlohy

Rob ich v tomto poradí. Každá má akceptačné kritériá.

### 1. Nadpisy v šablóne (on-page, stredná priorita)

Na každej stránke sú tieto `<h2>` zo spoločnej šablóny, ktoré nepatria do obsahu:
- SK: „List do Veže osudu“, „List je zapečatený!“, „Čo by si tu chcel?“
- EN: ekvivalenty v EN šablóne

Zmeň ich na ne-nadpisové prvky (`<p class="…">` alebo `<div class="…">`) a zachovaj vzhľad (prenes triedu alebo uprav CSS selektor `h2` → trieda). Ak je nadpis potrebný pre prístupnosť dialógu, použi `aria-labelledby` na prvok s `id`, nie `<h2>`.

Odstráň prázdne nadpisy, ktoré dopĺňa JS:
- homepage: prázdny `<h3>` v karte hrdinu („Nový hrdina“)
- `/tvorba-postavy/` a `/en/character-creator/`: prázdny `<h2>`

Daj do nich predvolený text, alebo prvok vytvor až v JS spolu s obsahom.

Na `/navody/` a `/en/guides/` je poradie H1 → H3 (5 krokov) → H2 „Knižnica“. Pridaj nad kroky `<h2>` „Ako začať v 5 krokoch“ / „Getting started in 5 steps“.

**Hotovo, keď:** na žiadnej stránke nie je `<h2>`/`<h3>` zo šablóny ani prázdny nadpis a žiadna stránka nepreskakuje úroveň nadpisu.

### 2. Mobilný hero na homepage (stredná)

Na šírke 390 px je nad H1 dekoratívny obrázok d20 s runovým kruhom (~600 px výšky). H1, úvodný text aj tlačidlo „Začni hrať“ sú tak až na konci prvej obrazovky.

- Pod ~720 px daj text (H1, úvod, tlačidlá) **pred** obrázok (`order` vo flex/grid) a obrázok zmenši na max ~45vh.
- Zníž výšku cookie lišty na mobile (menší padding, text a tlačidlo v jednom riadku, ak sa zmestia).

**Hotovo, keď:** na 390×844 sú H1 aj tlačidlo „Začni hrať“ viditeľné bez scrollovania a CLS zostáva < 0,05.

### 3. Odkazy „Mapy kráľovstva“ v HTML (stredná)

Na homepage sú v surovom HTML v `<main>` len 4 odkazy, po vykreslení JS 14. Mapu teraz vkladá JS. Vygeneruj odkazy mapy (`/navody/`, `/tvorba-pribehu/`, `/tvorba-postavy/`, `/kocky/`, `/nastroje/` …) priamo v HTML na serveri. JS ich môže len oživiť (animácie), nie vytvárať.

**Hotovo, keď:** `curl -s https://d20.sk/` (alebo lokálny výstup) obsahuje v `<main>` všetky odkazy mapy.

### 4. Rozšírenie obsahu nástrojov (vysoká)

Nástroj nechaj hore. Obsah daj **pod nástroj** v sémantických sekciách (H2/H3, odseky, zoznamy).

**`/kocky/` a `/en/dice-roller/`** (dnes ~70 slov) → 400–600 slov:
- H2 „Aké kocky sa používajú v DnD“: d4, d6, d8, d10, d12, d20, d% a na čo slúžia
- H2 „Ako čítať zápis 2d6+3“
- H2 „Výhoda a nevýhoda“
- H2 „Časté otázky“: 4–6 otázok s odpoveďami po 40–60 slovách (napr. „Koľko kociek potrebujem na DnD?“, „Čo znamená kritický zásah?“, „Je online hod férový?“)
- odkazy na `/harok-postavy/`, `/tracker-suboja/`, `/navody/`

**`/tvorba-postavy/` a `/en/character-creator/`** (dnes ~90 slov) → 500–700 slov:
- H2 „Tvorba postavy v 6 krokoch“: druh → povolanie → vlastnosti → pozadie → výbava → meno a príbeh
- H2 „Ako rozdeliť vlastnosti“: štandardné pole 15, 14, 13, 12, 10, 8 vs. hod 4d6
- H2 „Časté otázky“ (3–5)
- odkazy na `/rasy/`, `/povolania/`, `/harok-postavy/`, `/generator-npc/`

**`/navody/` a `/en/guides/`** (dnes ~240 slov): rozšír 5 krokov na plnohodnotný návod (spolu 1 000+ slov) a pridaj blok „Časté otázky“ (Čo je DnD? Koľko hráčov treba? Ako dlho trvá hra? Potrebujem knihy? Čo robí DM?).

Na stránky s FAQ blokom pridaj do `@graph` `FAQPage` presne s tými otázkami a odpoveďami, ktoré sú viditeľné na stránke.

**Hotovo, keď:** každá stránka má aspoň uvedený počet slov vlastného textu (bez navigácie, formulára a pätičky), SK a EN si obsahovo zodpovedajú, titulky a popisy zostali.

### 5. Stránka „O projekte“ a autor (vysoká)

- Vytvor `/o-projekte/` a `/en/about/` v rovnakej šablóne: čo je d20.sk, prečo vznikol, kto ho robí, licencia SRD a upozornenie na ochrannú známku, kontakt (odkaz na existujúci formulár).
- Údaje o autorovi: meno **Matúš Šturdík** (je už v schéme ako `publisher`). Všetko ďalšie (skúsenosti s DnD, profily) nechaj ako `TODO(majiteľ)`.
- Pridaj stránku do sitemapy (s hreflang trojicou sk/en/x-default ako ostatné), do pätičky v oboch jazykoch, s `BreadcrumbList` a `AboutPage`.
- Do JSON-LD pridaj entitu autora a odkazuj na ňu:

```json
{"@type": "Person", "@id": "https://d20.sk/#autor", "name": "Matúš Šturdík",
 "url": "https://d20.sk/o-projekte/", "sameAs": ["TODO(majiteľ): URL profilov"]}
```

`WebSite.publisher` a `author`/`publisher` ostatných stránok zmeň na `{"@id": "https://d20.sk/#autor"}`. Ak majiteľ profily nedodá, `sameAs` vynechaj, nenechávaj v ňom placeholder na produkcii.

**Hotovo, keď:** stránky existujú v oboch jazykoch, sú v sitemape a v pätičke, vracajú 200, majú self-canonical a obojsmerný hreflang a JSON-LD sa dá bez chyby sparsovať.

### 6. Dátumy a drobnosti v schéme (stredná / nízka)

- Na návodoch a referenčných stránkach (`/navody/`, `/povolania/`, `/rasy/`, `/slovnik/` + EN) zobraz „Aktualizované: D. M. RRRR“ / „Updated: Month D, YYYY“ a pridaj `dateModified` (ISO 8601) do `WebPage`. Dátum ber z rovnakého zdroja ako `lastmod` v sitemape, aby sa zhodovali.
- `WebApplication.name` je teraz celý titulok („Generátor NPC do DnD: mená, povaha, tajomstvá | d20.sk“). Zmeň ho na čistý názov bez „ | d20.sk“ (napr. „Generátor NPC do DnD“).

### 7. Kontextové odkazy medzi nástrojmi (stredná)

Pod každým nástrojom pridaj sekciu „Súvisiace nástroje“ / „Related tools“ s 2–4 odkazmi a jednou vetou ku každému:
- NPC ↔ krčma ↔ poklad ↔ tvorba príbehu
- kocky ↔ hárok postavy ↔ tracker súboja
- tvorba postavy ↔ povolania ↔ rasy ↔ hárok postavy

Text odkazov má byť popisný („generátor krčmy“), nie „klikni sem“.

### 8. Server: hlavičky a kompresia (nízka)

Ak je konfigurácia nginx v repozitári, doplň (inak priprav snippet do `docs/nginx-seo.conf` a uveď to v súhrne):

```nginx
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' https://static.cloudflareinsights.com; connect-src 'self' https://cloudflareinsights.com; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'" always;
brotli on;
brotli_types text/css application/javascript application/json image/svg+xml text/plain application/xml;
```

CSP najprv nasaď ako `Content-Security-Policy-Report-Only` a over, že konzola nehlási porušenia na žiadnej stránke (inline JSON-LD je v poriadku, inline skripty treba presunúť do súborov alebo povoliť hashom). `brotli` vyžaduje modul `ngx_brotli`. Ak ho server nemá, vynechaj ho.

### 9. llms.txt (nízka)

Vytvor `/llms.txt`: názov, jednovetový popis webu a zoznam hlavných stránok (SK aj EN) vo formáte `- [Názov](URL): krátky popis`. Do sitemapy ho nepridávaj.

### 10. 3D kocky (nízka)

Na `/kocky/` je na desktope ~160 ms blokovania hlavného vlákna (3D). Ťažkú 3D časť inicializuj až po prvej interakcii alebo v `requestIdleCallback`, s ľahkým statickým náhľadom kocky do tej doby. Výsledok hodu musí zostať férový a rovnaký ako dnes.

## Mimo rozsahu agenta (urobí majiteľ)

- Overenie v Google Search Console a Bing Webmaster Tools, odoslanie sitemapy, IndexNow.
- Predstavenie webu komunite (Discord D&D Slovakia, RPG skupiny, Reddit) a spolupráce pre spätné odkazy.
- Doplnenie `TODO(majiteľ)` údajov o autorovi.
- Ilustrácie povolaní a rás a vlastné OG obrázky (vyžadujú grafiku).

## Overenie

Po zmenách spusti web lokálne (alebo na stagingu) a over:

```bash
BASE=http://localhost:8080   # uprav podľa projektu
for u in $(curl -s $BASE/sitemap.xml | grep -o '<loc>[^<]*' | sed 's/<loc>//; s#https://d20.sk#'$BASE'#'); do
  html=$(curl -s "$u")
  code=$(curl -s -o /dev/null -w '%{http_code}' "$u")
  h1=$(grep -o '<h1' <<<"$html" | wc -l)
  empty=$(grep -cE '<h[1-4][^>]*>\s*</h[1-4]>' <<<"$html")
  tpl=$(grep -cE '<h2[^>]*>(List do Veže osudu|List je zapečatený!|Čo by si tu chcel\?)' <<<"$html")
  echo "$code h1=$h1 empty=$empty tplH2=$tpl $u"
done
```

Očakávané: všade `200 h1=1 empty=0 tplH2=0`. Ďalej over:
- JSON-LD každej stránky sa dá sparsovať (`python3 -c 'import json,sys; json.loads(sys.stdin.read())'` na obsah každého `<script type="application/ld+json">`) a prejde v [Rich Results Test](https://search.google.com/test/rich-results) alebo na [validator.schema.org](https://validator.schema.org/).
- Hreflang je pri každej novej stránke obojsmerný (sk ↔ en, x-default = sk).
- Lighthouse (mobil) pre `/`, `/kocky/`, `/tvorba-postavy/`: LCP < 2,5 s, CLS < 0,1, SEO 100.
- Screenshot homepage na 390×844: H1 aj „Začni hrať“ sú nad ohybom.

## Výstup

Na konci napíš súhrn:
1. zoznam zmenených súborov podľa úloh,
2. čo sa nepodarilo alebo čo si vynechal a prečo,
3. všetky `TODO(majiteľ)` s presným miestom v kóde,
4. výsledok overovacieho skriptu.
