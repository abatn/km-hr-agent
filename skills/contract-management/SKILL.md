---
description: Arbeitsvertrag-Prüfung (Contract Preflight) – Gehalt gegen Mindestlohn, Formfall-Hinweise (Schriftform/Textform/QES), NachwG-Pflichtangaben-Checkliste. Agent prüft NIE, erstellt/signiert NIE (Variante A).
---

## Funktionierende MCP-Connector

| Connector | Tool | Zweck | Auth |
|---|---|---|---|
| `filesystem` | `read_text_file` | Spec + Link-Katalog + Vorlage lesen (`knowledge/legal/contract-*.md`, `knowledge/templates/contract-templates/`) | Keine |
| `ansvar-german-law` | `search`, `validate_citation`, `get_provision` | Normtexte prüfen: §126a/§623/§611a BGB, §2 NachwG, §14 TzBfG, §1 MiLoG | ✅ OAuth |
| `fetch` | `fetch` (mcp-server-fetch) | URLs aus dem Link-Katalog verifizieren (Abrufdatum) – **keine hartkodierten Links** | Keine |

**Kein Signatur-Connector.** Signatur-Option A–F bleibt User-Entscheidung (`knowledge/legal/contract-management.md` §4).

---

## Link-Regel (USER-GO 24.09.2026)

- **Single Source of Truth für URLs:** `knowledge/legal/contract-sources.md`
- Code liest dieses MD und parst Markdown-Links zur Laufzeit.
- **0 `https://`-String-Literals in Python** (Projektregel, siehe contract-sources.md §D).

---

## Schritte (Contract Preflight, HR-Klick-triggered)

### 1. Bewerbungsdaten laden
- `queue_agent_task("contract_preflight", {"application_id": …, "candidate_id": …, "trigger": "hr_onboarding_klick"})`
- Runner: Kandidat + Job + Gehalt aus SQLite (`candidates`, `jobs`, `applications`)

### 2. Mindestlohn-Check (DE)
- **Wert einlesen aus** `knowledge/legal/contract-sources.md` (Key `mindestlohn_2026`, 13,90 €/h Stand 2026, Quellenstatus sekundär)
- Stundenlohn (oder Jahresgehalt/1720) ≥ Mindestlohn → ✅ / sonst ❌
- Kein Gehalt in der Stelle → ⚠️ HINWEIS (Design-Entscheidung, kein FEHLER – Parität zu `app.py` MiLoG-Logik)

### 3. Formfall-Hinweise (statisch aus Spec §4 + Link-Katalog)
- Befristet? → §14 Abs.4 TzBfG Schriftform → nur QES elektronisch (§126a BGB)
- Kündigung/Aufhebung im Lauf? → §623 BGB: elektronische Form ausgeschlossen
- Unbefristet + unstrittig? → formfrei (§611a) + NachwG-Nachweis in Textform (§2)
- QES = eIDAS Art. 25(2) (Link aus Katalog)

### 4. NachwG-Checkliste (§2 Abs.1 Nr.1–15)
Volltext aus `contract-sources.md` Key `nachwg_2` → Report listet alle 15 Pflichtangaben zum manuellen Abhaken (HR erstellt den Vertrag, Agent nur prüft).

### 5. Vertragsskelett
- Vorlage: `knowledge/templates/contract-templates/arbeitsvertrag-de-skeleton.md`
- Report verlinkt die Vorlage (Pfad, kein externer Link)

### 6. Ergebnis
- `ergebnisse/contract-preflight-bewerbung-{id}.md` mit: Gehaltsverdict, Formfall-Tabelle, NachwG-Checkliste, Quellen-Tabelle (aus Link-Katalog geparst, mit Abrufstatus)
- Sichtbar in 📄/🔎 Agent-Details (result_path) – **kein neuer Tab**

---

## Compliance-Score (Preflight)

| Status | Bedeutung | Aktion |
|---|---|---|
| ✅ | Gehalt ≥ Mindestlohn, Formfall-Hinweise erzeugt | HR erstellt Vertrag weiter |
| ⚠️ | Kein Gehalt angegeben | Hinweis, HR ergänzt Gehalt |
| ❌ | Gehalt < Mindestlohn | Vertrag nicht aushändigen – HR prüfen |

---

## Verantwortlichkeit (Variante A)

- **Agent:** prüft, schreibt Report, verlinkt Quellen. **Nie** Vertrag erstellen, **nie** signieren, **nie** Status ändern.
- **HR:** erstellt Vertrag aus Vorlage, prüft Report, wählt Formfall, lässt unterschreiben, händigt aus (NachwG).
- **Kandidat:** prüft + unterschreibt (je nach Formfall handschriftlich/QES).
