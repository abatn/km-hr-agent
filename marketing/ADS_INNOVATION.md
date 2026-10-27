# ADS-INNOVATION — agentische Wege zur Aufmerksamkeit

**Stand:** 28.10.2026 · **Ersetzt als Leitlinie:** die reinen Suchkanäle aus `ADS_ALTERNATIVEN.md` (Google/Microsoft bleiben als Fallback).
**Prototyp:** `scripts/jobs_x402_feed.py` · **Tests:** `tests/test_jobs_x402_feed.py` (x402-Testnetz, `.venv-ads`).

## 1. Selbstkritik

Google Ads und Microsoft Advertising sind **für Menschen gebaut**, und ein Agent ist darin nur ein Werkzeug auf einem menschlichen Konto:

- **Konto und Zahlung:** Ein Werbekonto braucht eine Rechtsperson, eine Zahlungskarte oder Rechnung und eine menschliche Freigabe. Ein Agent kann das nicht selbst erledigen, ohne dass ein Mensch dahintersteht.
- **Zugang über den Nutzer:** Der Zugriff läuft per OAuth-Zustimmung eines Menschen. Der Agent handelt im Auftrag, aber er ist nicht selbst Vertragspartner.
- **Ziel ist der Mensch am Bildschirm:** Klicks und Impressionen messen Aufmerksamkeit bei Menschen. Ein Agent, der eine Stelle findet, erzeugt keinen Klick, sondern einen Aufruf.
- **Gebote sind Auktionen für Menschen:** Das Modell aus `ads_agent.py` (CPM-Gebote) ist ein Abbild davon. Ein Agent braucht keine Auktion, er braucht einen **Preis pro Antwort**.

Ich habe mich außerdem geirrt, als ich x402-Netzwerke als „nicht geeignet“ abgetan habe. Ich hatte nur nach Plattformen für **menschliche** Zielgruppen gesucht. Eine Plattform, deren Nutzer Agenten sind, kann die Zielgruppe trotzdem erreichen: Der Agent eines Kandidaten **ist** die Aufmerksamkeit des Kandidaten.

## 2. Recherche (Auswahl)

| Quelle | Befund |
|---|---|
| **x402 Bazaar** (CDP, PayAI, docs.x402.org) | Indexer listen kostenpflichtige Endpunkte automatisch, wenn die 402-Antwort eine **Bazaar-Deklaration** trägt. Ranking nach Nutzerreichweite, Transaktionsvolumen, Beschreibungsqualität. MCP-Server für Agenten (`search_resources`, `proxy_tool_call`). |
| **Bazaar-Marktgröße** (OpenSea-Eintrag, Job-Tool) | Ein Stellen-Tool: 414 Aufrufe und 5 Zahler in 7 Tagen, rund $0,83 Volumen. **Der Markt ist heute sehr klein.** |
| **Instinct** (x402ads.io, Dexter) | Werbetreibende zahlen **nur bei Konversion**: wenn ein Agent nach einer Empfehlung den beworbenen Endpunkt tatsächlich bezahlt. Auf Solana. |
| **Operon** (operon.so/x402) | Native Platzierungen in Agentenantworten, Mindestbetrag 100 USDC, Vertrauenswert aus Verlässlichkeit. |
| **hive-ad-bid**, **picoads**, **AD-402**, **AgentReach** | Agentenseitige Auktionen oder Empfehlungs-Routing, zahlen per Impression oder Klick. |
| **Basemate „Agent Ads“** | Pay-per-Human über Gruppenchats mit Einwilligung (XMTP). Zeigt, dass Einwilligung als Produktregel machbar ist. Für Personalwerbung riskant. |
| **arXiv 2601.19435** (Ad insertion in LLM responses) | Auktionen über „Genres“ statt Keywords, VCG-Mechanismus, Trennung von Anzeige und Antwortgenerierung. Setzt voraus, dass man einen LLM-Kanal **besitzt**. |
| **arXiv 2610.14646** (AffMyerson) | Korrelierte Gebote, wenn Agenten dieselbe Unterhaltung lesen. Interessant für Auktionsdesign, nicht für unsere Umsetzung. |
| **arXiv 2608.27382** (LAMA, Token-Level-Werbung) | Werbung im Generierungsprozess. Forschung, kein Produkt. |
| **Agentic Recruitment Protocol (ARP, jinzaix)** | Entwurf: Kandidaten-Agenten, Arbeitgeber und Recruiting-Dienste sprechen REST und MCP. Stellen sind per Agent auffindbar und bewerbbar. |
| **A2A-Agent-Cards und MCP als Registry** (a2a-samples, Agennect, Agent Registry) | Agenten finden einander über Karten unter `/.well-known/agent-card.json`. Vertrauen und Bezahlung sind noch nicht standardisiert. |

## 3. Fünf Ideen, bewertet

Bewertung 1 (schlecht) bis 5 (sehr gut). Umsetzbarkeit mit unserer x402-Infrastruktur heißt: vorhandener Code aus `flight-agent` und `km-hr-agent` (Schranke, Käufer, Bazaar-Deklaration).

| # | Idee | Innovation | Umsetzbarkeit (x402) | Unabhängigkeit von Werbenetzen | Bemerkung |
|---|---|---|---|---|---|
| 1 | **Agentischer Stellenfeed über x402-Bazaar** (Agenten suchen und zahlen je Anfrage) | 4 | 5 | 5 | Prototyp gebaut (Testnetz). Die Bazaar ist die Discovery-Schicht. |
| 2 | **Konversions-Anzeige in Agentenantworten** (wie Instinct: nur bezahlen, wenn ein Agent den Endpunkt tatsächlich nutzt) | 5 | 2 | 3 | Baut auf Idee 1 auf. Braucht Netzwerkpartner, Solana oder Mainnet-Geld. |
| 3 | **Recruiting-Agent mit A2A-Karte und ARP-Schnittstelle** (Kandidaten-Agent verhandelt mit Arbeitgeber-Agent) | 4 | 3 | 4 | Hohe Reichweite bei Agenten, aber Einwilligung und Datenschutz sind schwer. |
| 4 | **Pay-per-Human mit Einwilligung** (Basemate-Muster) | 3 | 2 | 3 | Für Kandidatenansprache zu nah an unerwünschter Werbung. Nicht empfohlen. |
| 5 | **Genre-Auktion in fremden LLM-Antworten** (arXiv 2601.19435) | 5 | 1 | 1 | Wir besitzen keinen LLM-Kanal, also kein Umsetzungspfad. |

## 4. Empfehlung: Idee 1

**Die revolutionärste Idee, die sich umsetzen lässt, ist die Stellensuche als bezahlte Agenten-API (Idee 1).** Begründung:

- **Der Agent ist der Kunde.** Ein Kandidaten-Agent oder ein Arbeitgeber-Agent sucht und zahlt pro Anfrage in USDC. Es gibt kein Konto, keine Karte, keine Freigabe durch einen Werbemanager.
- **Discovery ist eingebaut.** Die Bazaar-Deklaration macht den Dienst für fremde Agenten auffindbar. Nach den Regeln der Bazaar zählen Nutzung und Beschreibungsqualität, nicht Werbebudget.
- **Der Code existiert.** `flight-agent` hat Schranke, Käufer und Bazaar-Deklaration bereits. Der Prototyp verwendet dasselbe Muster für Stellen.
- **Keine Werbung, also kein Datenhandel.** Der Feed liefert nur öffentliche Stellenfelder. Personenbezug wird durch den PII-Guard und den Nur-Lese-Zugriff ausgeschlossen.
- **Idee 2 hängt daran.** Konversionsbasierte Werbung braucht einen Endpunkt, der bezahlt werden kann. Idee 1 schafft diesen Endpunkt.

**Ehrliche Grenze:** Der Markt für bezahlte Agenten-Stellensuche ist heute winzig (siehe Bazaar-Zahlen). Der Wert liegt im Aufbau einer Position, bevor der Markt wächst, nicht im heutigen Umsatz.

## 5. Prototyp (Dry-Run, Testnetz)

`scripts/jobs_x402_feed.py` (FastAPI, x402-Schranke, Bazaar-Deklaration):

- `GET /api/agent/jobs?q=…&land=DE&limit=…`
- Ohne Zahlung: HTTP 402 mit `payment-required`-Header, der die Bazaar-Deklaration (`extensions.bazaar`) trägt.
- Mit Zahlung: 200, Liste öffentlicher Stellen, `sponsored: false`.
- Nur Testnetz (`eip155:84532`); Mainnet wird beim Aufbau abgelehnt.
- Datenbank nur lesend (`mode=ro`), PII-Guard auf jedes Textfeld.

Test-Nachweis (`tests/test_jobs_x402_feed.py`, 7 Tests, grün): 402 mit Bazaar-Deklaration (GET, Ressourcen-URL), bezahlte Suche mit echter Zahlung über Mock-Facilitator, Stichwortfilter, Limit, Mainnet-Sperre, PII-Sperre, nur-lesender Zugriff.

## 6. Offene Punkte

- **Mainnet-Listung** erst nach Freigabe. Bis dahin nur Testnetz. Kein echter Geldfluss.
- **Bazaar-Listung** prüfen: Indexer akzeptieren Testnetz-Ressourcen nach der Doku nicht unbedingt. Vor einer Listung den Facilitator-Status prüfen.
- **Beschreibungsqualität** ist ein Rankingsignal. Die Beschreibung im Feed ist eine Erstfassung.
- **Solana oder EVM:** Instinct nutzt Solana. Für Idee 2 wäre ein zweiter Zahlungsweg nötig.
- **Einwilligung** entfällt bei öffentlichen Stellen. Bei Kandidatendaten (Idee 3) gelten die DSGVO-Regeln.

## Quellen

- x402 Bazaar (CDP): https://docs.cdp.coinbase.com/x402/bazaar · PayAI: https://docs.payai.network/x402/facilitators/bazaar
- x402-Bazaar-Spezifikation: https://github.com/x402-foundation/x402/blob/main/specs/extensions/bazaar.md
- Instinct: https://x402ads.io/ · Operon: https://operon.so/x402
- hive-ad-bid: https://github.com/srotzin/hive-ad-bid · Basemate Agent Ads: https://github.com/fweekshow/Agent-Ads-by-Basemate
- arXiv 2601.19435 (Ad insertion in LLM responses) · arXiv 2610.14646 (AffMyerson) · arXiv 2608.27382 (LAMA)
- Agentic Recruitment Protocol: https://github.com/jinzaix/agentic-recruitment-protocol
- A2A mit MCP als Registry: https://github.com/google-a2a/a2a-samples
