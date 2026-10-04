# C2-Service — Personio-Connector (Spec, MD-first)

> **Status (26.09.2026): STAGING, Schritt 1 von 3 (§H-14).** Schritt 2 (`opencode.json`)
> und Schritt 3 (Zählwerk) laufen **erst nach separatem GO des Nutzers** — C2 bleibt laut
> `ergebnisse/entscheidungen.md:2286` gesperrt, bis Variante bestätigt ist.
> Stand Konnektor-Ökosystem: **14** Server (`jitsi-meeting` am 27.09.2026 entfernt, 0 Aufrufe; VDO.Ninja-Migration).

## Zweck
C2 = externer HR-Dienst (Personio) für Kandidaten-/Bewerberdaten, **nur Read**, keine Schreibrechte.

## Auswahlkriterien (alle = Design-Entscheidung, keine Quelle fordert sie)
- Lizenz MIT/Apache bevorzugt · lokale Ausführung (stdio) bevorzugt · Wartung < 12 Monate
- **DSGVO-Property:** keine Kandidatendaten nach außen, nur Suchbegriffe (Muster: `mcp-connector-config.md` Datenschutzvermerk)

## Shortlist (Quelle: `ergebnisse/recherche-plan-restpunkte-2026-09-25.md:11-40`, GitHub-API + Support-Abruf 25.09.2026)
| Kandidat | Lizenz | Wartung (pushed_at) | Bewertung |
|---|---|---|---|
| `borgels/mcp-server-personio` | Apache-2.0 | 23.09.2026 | ✅ **Empfehlung (b)** |
| `NikolaiGoMedicus/personio-mcp-server` | MIT | 26.07.2026 | ✅ Reserve |
| `vanman2024/cats-mcp-server` | **keine Lizenz** | 19.09.2026 | ⚠️ Ausschluss |
| `stefanoamorelli/lever-mcp` | AGPL-3.0 | — | ⚠️ Ausschluss (Copyleft) |
| `alexmeckes/greenhouse-mcp` | MIT | > 1 Jahr inaktiv | ⚠️ Ausschluss |
| Personio Vendor-MCP (offiziell, Beta seit 31.08.2026) | Vendor-Beta, nur Read | — | Variante (a): externer Vendor-Zugang |

**Empfehlung:** Variante **(b)** `borgels/mcp-server-personio` (Apache-2.0, aktiv 23.09.2026).
**Nicht belegbar (ehrlich):** stdio-Laufzeit ohne README-Abruf (Tool-Ausfall am 25.09.2026); Checkr-Repo nur Dritt-Listing; **kein** MCP für Urkunden-/Zeugnis-Validierung gefunden (Treffer = Faktencheck).

## Bauplan (Reihenfolge)
1. Diese Spec (MD) — vorbereitet (§H-14)
2. `opencode.json`: 1 Server unter `mcp` eintragen — **in §H-Runde H5-verboten, erst nach GO**
3. Zählwerk in 6 Stellen (AGENTS.md:70 · README.md:3/:39 · knowledge.md:80 · mvp.md:34/:70/:87 · instructions.md) — **erst nach D2-Entscheidung** (sonst 15→16 vs. 14→15-Konflikt)
4. `tests/e2e_c2_connector.py` (Handshake `initialize` + `tools/list`) — rot vor Schritt 2, grün danach

## Offene Frage (Antwort Slot 14)
> (a) Personio-Vendor-Beta · **(b) borgels (Empfehlung)** · (c) keinen — C2 gestrichen?
