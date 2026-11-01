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
