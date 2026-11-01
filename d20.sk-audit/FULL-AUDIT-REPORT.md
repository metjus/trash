# SEO audit: d20.sk

**Dátum:** 1. 11. 2026 · **Nástroj:** claude-seo v2.5.0 (metodika seo-audit) · **Rozsah:** 30 URL (15 SK + 15 EN), celá sitemapa

## Zhrnutie

**SEO Health Score: 80 / 100**

| Kategória | Váha | Skóre |
|---|---|---|
| Technické SEO | 22 % | 90 |
| Kvalita obsahu | 23 % | 68 |
| On-page SEO | 20 % | 82 |
| Schema / štruktúrované dáta | 10 % | 85 |
| Výkon (CWV) | 10 % | 95 |
| Pripravenosť na AI vyhľadávanie | 10 % | 60 |
| Obrázky | 5 % | 75 |

**Typ webu:** obsahový web s nástrojmi (fanúšikovský publisher), slovensko-anglický. Nejde o lokálny biznis ani e-shop.

d20.sk má technicky nadpriemerný základ. Všetky stránky vracajú 200 a majú unikátne titulky a popisy, presne jeden H1, správny canonical, obojsmerné hreflang SK↔EN a štruktúrované dáta. Načítajú sa rýchlo a nič na nich neposkakuje. Body strácajú hlavne tieto veci:

1. **Slabá viditeľnosť a autorita mimo webu.** Vyhľadávanie „d20.sk“ nenašlo žiadnu zmienku o webe a nenašiel som ani spätné odkazy. Web je nový (lastmod október 2026).
2. **Tenký obsah na kľúčových nástrojoch.** `/kocky/` má asi 68 slov vlastného textu, `/tvorba-postavy/` asi 99 a homepage asi 160.
3. **Chýbajú signály E-E-A-T.** Nie je tu stránka „O nás“ ani autor, návody nemajú dátum a chýbajú externé zdroje.
4. **Šum v nadpisoch.** Na každej stránke sú H2 z formulára a pätičky („List do Veže osudu“, „List je zapečatený!“) a niektoré nadpisy sú prázdne.
5. **Mobil:** H1 a úvodný text sú pod veľkým obrázkom kocky a cookie lišta ich prekrýva.

**Top 5 rýchlych výhier**
1. Overiť web v Google Search Console a Bing Webmaster Tools a odoslať sitemapu.
2. Zmeniť H2 formulára a pätičky na `<p>`/`<div>` a odstrániť prázdne nadpisy.
3. Doplniť na `/kocky/` a `/tvorba-postavy/` 300 až 500 slov návodu a FAQ.
4. Pridať stránku „O projekte“ s autorom a prepojiť ju so schémou (`Person`/`Organization` + `sameAs`).
5. Na mobile posunúť H1 nad obrázok kocky alebo obrázok zmenšiť.

> **Obmedzenia auditu:** Nie sú pripojené Google Search Console, GA4, CrUX, Moz ani DataForSEO, takže chýbajú reálne dáta o indexácii, pozíciách, návštevnosti a spätných odkazoch. Rýchlosť som meral laboratórne v Chromiu cez sieťový proxy, takže TTFB je mierne nadhodnotený. Presmerovanie z `http://` som nemohol otestovať, lebo proxy obyčajné HTTP neprepúšťa. Interné skripty claude-seo si overujú DNS samé, preto som dáta zbieral curl-om a Chromiom a vyhodnotil ich podľa metodiky skillu.

---

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

## Kvalita obsahu (68)

**Čo funguje**
- Referenčné stránky sú hodnotné a štruktúrované: `/povolania/` (~880 slov vlastného textu), `/rasy/` (~690), `/slovnik/` (~820) a generátory NPC, krčmy a pokladu (1 100 až 1 550).
- Text je prirodzený, zrozumiteľný a písaný pre začiatočníkov, s anglickými originálmi pojmov („Barbar · Barbarian“). To pomáha aj pri vyhľadávaní v angličtine.
- Licencia SRD 5.1/5.2 (CC BY 4.0) a upozornenie na ochrannú známku Wizards of the Coast sú v pätičke.
- Slovenská nika má veľmi slabú konkurenciu. Vyhľadávanie slovenských návodov a generátorov DnD nenašlo žiadny ucelený slovenský zdroj, len české alebo anglické.

**Nálezy**

| Závažnosť | Nález | Odporúčanie |
|---|---|---|
| Vysoká | Tenký obsah na nástrojoch s najväčším potenciálom hľadanosti: `/kocky/` ~68 slov, `/en/dice-roller/` ~70, `/tvorba-postavy/` ~99, `/en/character-creator/` ~83 (bez navigácie, formulára a pätičky). | Pod nástroj doplniť 300–500 slov: ako funguje hod, čo je výhoda/nevýhoda, ktoré kocky sa na čo používajú, FAQ („Aké kocky potrebujem na DnD?“, „Čo je d20?“). |
| Vysoká | Chýbajú signály E-E-A-T. Nie je tu stránka „O projekte“ ani autor, iba meno vydavateľa v schéme. Návody nemajú dátum vydania ani aktualizácie. | Vytvoriť `/o-projekte/` a `/en/about/` s tým, kto web robí a aké má skúsenosti s DnD. Pri návodoch zobraziť „Aktualizované: …“. |
| Stredná | Homepage (~160 slov) a `/navody/` (~225 slov) sú rozcestníky s málom textu. `/navody/` cieli na silný dopyt „ako hrať DnD“. | `/navody/` rozšíriť na plnohodnotný návod (1 000+ slov) alebo z neho spraviť hub s podstránkami (pravidlá, prvé sedenie, ako byť DM). |
| Stredná | Žiadne odkazy na externé zdroje okrem právnych stránok. | Odkázať na oficiálne SRD a D&D Beyond pri pravidlách. Zvyšuje to dôveryhodnosť. |
| Nízka | Rovnaký veľký blok textu („List do Veže osudu“, cookie lišta, pätička) má každá stránka v HTML (~250 slov). | Je to v poriadku, len to zväčšuje pomer šablóny k obsahu na krátkych stránkach. Ďalší dôvod rozšíriť obsah nástrojov. |

**Príležitosti na nový obsah** (slovenská nika je takmer prázdna): jednotlivé povolania a rasy na samostatných URL (`/povolania/bojovnik/` …), návod „Ako byť Dungeon Master“, „Prvé sedenie krok za krokom“, slovník kúziel, hotové jednorazové dobrodružstvo na stiahnutie a prehľad slovenských DnD komunít.

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

## Výkon (95)

Laboratórne meranie v Chromiu (desktop 1366×900, mobil 390×844), 5 reprezentatívnych stránok:

| Stránka | LCP desktop | LCP mobil | CLS | TBT | Prenos |
|---|---|---|---|---|---|
| `/` | 1,50 s | 1,07 s | 0,000 | 0 ms | ~215 kB |
| `/povolania/` | 1,22 s | 1,05 s | 0,001 | 0 ms | ~190 kB |
| `/kocky/` | 1,24 s | 1,17 s | 0,000 | 160 ms (desktop, 3D) | ~340 kB |
| `/generator-npc/` | 1,06 s | 1,08 s | 0,000 | 0 ms | ~210 kB |
| `/tvorba-postavy/` | 1,04 s | 1,11 s | 0,026 | 0 ms | ~205 kB |

Všetky stránky sú hlboko v pásme „dobré“ (LCP < 2,5 s, CLS < 0,1). Žiadne chyby v konzole ani zlyhané požiadavky. LCP prvkom je text, nie obrázok. Fonty sa prednačítajú, JS je rozdelený po stránkach a ~20 požiadaviek na stránku je v poriadku.

| Závažnosť | Nález | Odporúčanie |
|---|---|---|
| Nízka | TTFB 0,57–0,82 s (meraný cez proxy, reálne pravdepodobne nižší). | Overiť v PageSpeed Insights. Pri TTFB > 0,6 s zvážiť cache HTML na Cloudflare edge. |
| Nízka | 3D kocky na desktope majú 160 ms blokovania hlavného vlákna. | 3D knižnicu načítať až po prvej interakcii alebo cez `requestIdleCallback`. |
| Info | INP sa v laboratóriu nedá zmerať. | Po nazbieraní návštevnosti sledovať CrUX alebo Search Console. |

## Vizuál a mobil

Screenshoty sú v priečinku `screenshots/`.

- Dizajn je výrazný a tematický (fantasy, pergamen, zlato) a tvorí silnú značku. Na šírke 390 px nič nepretečie horizontálne.
- **Stredná:** Na mobile je nad H1 obrovský dekoratívny obrázok d20 (~600 px). H1 a úvodný text sú až na spodku prvej obrazovky a tlačidlo „Začni hrať“ je pod ňou.
- **Stredná:** Cookie lišta na mobile prekrýva úvodný odsek. Text lišty („Nepoužívame cookies“) je skvelý, ale lišta je zbytočne vysoká.
- **Nízka:** Malé dotykové plochy (< 24 px): odkaz „Ochrana osobných údajov“ v pätičke, odkazy v breadcrumb a inline odkazy na `/tvorba-postavy/`.

## Obrázky (75)

- Na webe takmer nie sú obsahové obrázky. Všetky `<img>` sú logá a dekorácia so správnym `alt=""`, ilustrácie sú cez CSS alebo canvas.
- Logo má formát WebP so `srcset`. Hlavné logo má `width`/`height`. Boot a warp overlay (`logo-176.webp`) rozmery nemajú, ale sú skryté, takže CLS neovplyvňujú.
- **Stredná príležitosť:** Chýbajú ilustrácie povolaní a rás s popisným alt textom. Google Obrázky sú pri DnD silný kanál („dnd barbar“, „dnd character sheet“).
- **Nízka:** OG obrázok je jeden pre celý jazyk (`og-sk.jpg`/`og-en.jpg`). Vlastné OG obrázky pre nástroje by zvýšili preklikovosť pri zdieľaní na Discorde a Facebooku.

## Pripravenosť na AI vyhľadávanie (60)

**Čo funguje**
- robots.txt nijako neblokuje AI crawlery (GPTBot, ClaudeBot, PerplexityBot, Google-Extended).
- Obsah je v serverovom HTML a nie je závislý od JS. Jasné definície (slovník) a odseky sa dobre citujú.
- `DefinedTermSet` a kotvy na pojmy umožňujú presnú citáciu.

**Nálezy**

| Závažnosť | Nález | Odporúčanie |
|---|---|---|
| Vysoká | Žiadne zmienky o značke mimo webu. Vyhľadávanie „d20.sk“ nenašlo web ani odkazy naň. AI asistenti citujú hlavne zdroje, ktoré poznajú z iných webov. | Získať zmienky a odkazy z komunity: Discord D&D Slovakia (~1 400 členov), slovenské a české RPG fóra, Reddit r/DnD a r/Slovakia, herné obchody (Tlama Games, Ihrisko), blogy. |
| Stredná | Nie je overená indexácia v Google a Bingu. Bing je zdrojom pre ChatGPT search a Copilot. | Search Console + Bing Webmaster Tools a zapnúť IndexNow. |
| Nízka | Chýba `llms.txt`. | Voliteľné. Google ho ignoruje, niektoré AI nástroje ho čítajú. Stačí krátky zoznam hlavných stránok s popisom. |
| Nízka | Chýbajú krátke odpovede v štýle FAQ („Čo je DnD?“, „Koľko hráčov treba?“). | Pridať na `/navody/` blok FAQ s 40–60-slovnými odpoveďami. |

## Lokálne SEO, e-commerce, spätné odkazy

- **Lokálne / mapy:** nevzťahuje sa (web nie je lokálny podnik).
- **E-commerce:** nevzťahuje sa.
- **Spätné odkazy:** Moz, Bing ani DataForSEO nie sú pripojené. Podľa vyhľadávania web zatiaľ nemá viditeľné spätné odkazy, čo je pri novom webe očakávané.
- **Drift baseline:** neexistuje (prvý audit).
