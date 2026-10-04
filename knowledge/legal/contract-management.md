# Contract-Management (Punkt 8 – Phase-D-Review)

> **Stand:** 24.09.2026 (read-only Recherche **+ USER-GO Code-Go mit Recherche-Pflicht, Umsetzung gleicher Tag**)
> **Status Bipperz:** ⚠️ **teilweise** → **teilweise+ (Preflight-Report implementiert, Signatur weiterhin A–F offen)**
> **Hausregeln:** Beweis Datei:Zeile · Entscheidung bleibt beim User
> **Code-Go-Umfang (24.09.2026):** Recherche (`ergebnisse/phase-d-p8-contract-recherche.md`) ·
> Link-Katalog **nur MD** (`knowledge/legal/contract-sources.md`, 0 hartkodierte Links in Python) ·
> Vertragsskelett (`knowledge/templates/contract-templates/arbeitsvertrag-de-skeleton.md`) ·
> Skill 23 (`skills/contract-management/SKILL.md`) · HR-Button „Vertrags-Check" + Runner-Task
> `contract_preflight` (Gehalt vs. Mindestlohn 13,90 €/h Stand 2026, Formfall-Hinweise, NachwG-Checkliste).
> **Nicht in diesem GO:** Signatur-Dienst-Einbindung (A–F bleibt User-Wahl), Status-Tracking-DB.

---

## 1. Zweck + Bipperz-Status ⚠️ teilweise (Punkt 8)

**Zweck:** Spezifizieren, was Vertragsmanagement im KM-HR-Agenten heute schon
abdeckt, was ohne neuen Code legal/prüfbar machbar ist, und welche
Signatur-Optionen es gibt – ohne selbst Code zu schreiben oder einen
Connector zu entscheiden.

**Warum nur ⚠️ teilweise:**

- **Vorhanden (Kontext-Ebene):** Der Begriff „Arbeitsvertrag" erscheint
  ausschließlich als *Kontext* in Checklisten/Mails/Rechtstexten – z.B.
  `knowledge/templates/onboarding-templates/onboarding-de.md:12`
  („Arbeitsvertrag | Individueller Vertrag nach § 611 BGB | Vor Eintritt"),
  `knowledge/legal/visa-rules.md:158` („Arbeitsvertrag vorbereiten | Gehalt
  muss Mindestgehalt … erfüllen"), `scripts/agent-runner.py:420`
  (Onboarding-Mail-Text). Das ist Erwähnung, kein Feature.
- **Fehlt (Feature-Ebene):** Kein Vertragsgenerierungs-Workflow, kein
  Signatur-Workflow, keine Vertragsvorlage, kein Vertrags-Status-Tracking
  (nur manuelle Checklisten-Häkchen „Vertrag registriert",
  `onboarding-de.md:47`).
- **⚠️ Ehrlichkeitsvorbehalt (Lab-Prinzip 1):** Die Aufgabenstellung nennt
  „Bipperz-Status (Punkt 8)". Die Projektbelege kennen **kein** explizites
  „Bipperz-Vertragsmanagement": `ergebnisse/bipperz-konkurrenz-analyse.md:19-23`
  listet nur 3 Bipperz-Vorteile (E-Mail, Video, Kultur-Matching);
  Grep „Vertragsmanagement/contract-management" in knowledge/ + ergebnisse/
  = **0 Treffer**. Der ⚠️-Teil-Status bezeichnet daher den *eigenen* Stand
  (Kontext da, Feature fehlt), nicht eine belegte Bipperz-Anforderung.
  **Keine Erfindung: „Punkt 8" ist User-Vorgabe, kein zitierbarer Projektbeleg.**

---

## 2. Schritt-0-Befund (kein bestehendes Feature – Grep-Beweise)

Alle Greps am 24.09.2026, Wurzel `knowledge/ skills/ webui/ scripts/`.

| # | Grep | Treffer | Ergebnis |
|---|---|---|---|
| 1a | `grep -rni "vertrag" …` (inkl. `.bak`) | **38** | Nur Kontext (Vorbefund ~29 ohne Backups: **31** ohne `.bak`) |
| 1b | davon Feature „vertrag generieren/signieren" | **0** | z.B. `knowledge/legal/visa-rules.md:158` = Rechtskontext, `onboarding-de.md:12` = Checklisten-Eintrag |
| 2a | `grep -rni "signier" …` | **0** | kein Feature |
| 2b | `grep -rniE "e-sign\|esign\|…signatur" …` (Design gefiltert) | **0** | kein Feature |
| 2c | `grep -rniE "generier.*vertrag\|vertrag.*erstell\|…"` | **0** | kein Feature |
| 2d | Kombi-Muster `signier\|e-sign\|vertrag…(generier\|erstell\|versand)` (ohne `.bak`, ohne `design`) | **0** | **Gesamt: KEIN Feature** |

⚠️ **Methodik-Hinweis:** Der naive Pattern-Befehl mit `esign` liefert 150
Treffer, weil `esign` in „D**esign**-Entscheidung" matcht. Nach Präzisierung
(`grep -viE "design"`, Wortgrenzen): **0**.

**Rechtsgrundlagen-Inventar (je 2–3 Punkte mit Zeile):**

- `knowledge/legal/compliance-rules.md`
  - `:28` MiLoG = Mindestlohn, „Gehaltsangabe ≥ Mindestlohn"; `:37`
    Prüfpunkt „Gehalt ≥ Mindestlohn | MiLoG-Prüfung | **FEHLER**"
  - `:113/:131` CH: OR (Obligationenrecht) = Vertragsrecht,
    „OR Art. 319: Das Arbeitsverhältnis kann … eingegangen werden"
  - `:69` FR: Code du travail = „Vertragsbedingungen, Kündigungsfristen"
- `knowledge/legal/visa-rules.md`
  - `:42/:51-52` Blue Card §18g (Korrektur P4 26.09.2026, vorher §18b): Mindestgehalt 2026 **50.700 €**,
    Mangelberufe **45.934 €**
  - `:158` HR-Schritt „Arbeitsvertrag vorbereiten | Gehalt muss
    Mindestgehalt … (§18g: 50.700 € bzw. 45.934 €, Stand 2026) | Vor Visumantrag"
  - `:169` FR: Gehalt ≥ SMIC (~11.520 €/Jahr); `:178` CH: unbefristeter Vertrag
- `knowledge/legal/gdpr-policy.md`
  - `:32-35` Art. 6(1)(b) Vertragserfüllung (Daten vom Kandidaten selbst)
  - `:18/:63` Speicherbegrenzung 6 Monate; `dsgvo_cleanup()` 183 Tage
  - `:93` Drittländer → Standardvertragsklauseln (SCC)

**AGENTS.md Hardcoded-Werte (zitiert, Stand nach Recherche-Fix 24.09.2026):**

- `AGENTS.md:164` → `| MiLoG 13,90 EUR/h (Stand 2026) | … | ⚠️ Sekundär … vorher 12,41 (Stand 2025, veraltet) |`
  (Update-Befund: 12,41 = Wert 2025; 13,90 seit 01.01.2026 belegt via Link-Katalog `mindestlohn_2026`,
  **Quellenstatus: sekundär**, Primär-Rechtsverordnung am 24.09.2026 nicht abrufbar – siehe Recherche-Report §A)
- `AGENTS.md:165` → `| Blue Card 50.700/45.934 EUR | BAMF/ZAV (2026) | ✅ Offiziell |`

**ansvar-german-law Connector:**

- Konfiguration `opencode.json:34-38`:
  `"ansvar-german-law": { "type": "local", "command": ["npx","-y",
  "mcp-remote@0.1.38","https://gateway.ansvar.eu/mcp"], "enabled": true }`
- Aufgerufen via `mcp-remote` (OAuth, Free-Tier); Tools laut
  `knowledge/legal/compliance-rules.md:16-18`: `search`,
  `validate_citation`, `get_provision` + 28 weitere; Umfang **6.870 Gesetze**.
- **Connector-Verzeichnis `connectors/`:** existiert, enthält aber **nur**
  `hr-benchmark-server.py`, `salary-data-server.py`,
  `prescreen-config-server.py` – ansvar-german-law ist **nicht** lokal,
  sondern remote (gateway.ansvar.eu).
- **Scope:** ausschließlich **Gesetze** (Suche/Normtexte/Zitationen) –
  **keine Verträge**, keine Vertragserstellung, keine Signatur.

**Onboarding-Templates `knowledge/templates/onboarding-templates/` (alle 3 Dateien geprüft):**

| Datei | Vertraginhalt | Vertragsvorlage? |
|---|---|---|
| `onboarding-de.md:8-17,47` | Zeile „Arbeitsvertrag … § 611 BGB | Vor Eintritt" + Häkchen „Vertrag registriert" | **NEIN** |
| `onboarding-ch.md:8-17,47` | „Arbeitsvertrag … OR Art. 319 ff." + Häkchen | **NEIN** |
| `onboarding-fr.md:8-17,47` | „Contrat de travail CDI/CDD" + „Contrat enregistré" | **NEIN** |

→ **Befund: 0 Feature. Vertragsmanagement existiert nicht als Code/Workflow.**

---

## 3. Was JETZT legal/prüfbar ist – OHNE neuen Code

(alles nur MD/Checkliste; Gehaltsfeld-Validierung im Code wäre *Integrierbar*,
aber: **STOPP vor Code – User entscheidet**)

1. **Vorlagen-Checkliste gegen MiLoG/Blue-Card (rein MD, sofort umsetzbar):**
   Vor jeder Vertragsübergabe HR prüft (manuell, anhand bestehender Werte):
   - Stundenlohn ≥ **13,90 EUR/h** (Stand 2026; Quelle `knowledge/legal/contract-sources.md`
     Key `mindestlohn_2026`, **⚠️ sekundär** – vorher 12,41 veraltet)
     – Prüfpunkt existiert schon als Regel
     (`knowledge/legal/compliance-rules.md:37`, „FEHLER" bei Verstoß) + **Preflight-Report
     `contract_preflight` seit 24.09.2026 automatisiert**
   - Bei Nicht-EU-/Blue-Card-Fällen: Jahresgehalt ≥ **50.700 €** bzw.
     **45.934 €** (Mangelberuf, u.a. IT) (`AGENTS.md:165`,
     `knowledge/legal/visa-rules.md:51-52,158`)
   - Ergebnis dokumentieren wie bestehende Compliance-Reports
2. **Gehaltsfeld-Validierung im bestehenden Matching/Gehalt-Check
   integrierbar** (NACH User-Go, ist Code – hier nur Standort-Beweis):
   - `gehalt_check()` → `app.py:264` / `webui/logic.py:303`
     (Toleranz 0.8/1.1, `webui/logic.py:315-316` als Design-Entscheidung)
   - `berechne_match_score()` → `app.py:656` / `webui/logic.py:439`
   - MiLoG-Hinweis im Compliance-Report existiert bereits:
     `app.py:1604-1608` („MiLoG | Gehalt über Mindestlohn" bzw. „Kein
     Gehalt angegeben → HINWEIS")
3. **Signaturgrad-Checkliste für HR (MD):** vor Vertragsversand prüfen:
   befristet? → QES nötig (§ 14 Abs. 4 TzBfG + § 126a BGB, s. Abschnitt 4);
   Kündigung/Aufhebung? → elektronische Form gesetzlich ausgeschlossen
   (§ 623 BGB); unbefristet + unstrittig? → Textform/Schriftform-NachwG beachten.

---

## 4. Signatur-Optionen-Tabelle (Entscheidung User, KEIN Code)

**Rechtsrahmen vorab (Quellen):**

- **eIDAS VO (EU) 910/2014, Art. 25** (EUR-Lex, `eur-lex.europa.eu/eli/reg/2014/910/oj`):
  (1) Rechtswirkung darf einer e-Signatur *nicht allein* wegen elektronischer
  Form abgesprochen werden; **(2) QES hat die gleiche Rechtswirkung wie eine
  handschriftliche Unterschrift.** Grade in Art. 3: **SES** (einfach),
  **AES** (fortgeschritten), **QES** (qualifiziert).
- **DE-Sonderfall Arbeitsvertrag:**
  - Unbefristeter AV ist grundsätzlich **formfrei** (§ 611a BGB);
    Nachweispflicht § 2 NachwG – seit 01.01.2025 in begrenztem Umfang
    **Textform** möglich (Haufe 08.09.2025; Gleiss Lutz; Kanzlei Neuendorff
    16.11.2025: „Ab 2025 genügt in den meisten Fällen die Textform").
  - **Befristung:** § 14 Abs. 4 TzBfG Schriftform; elektronische Form
    *nicht ausgeschlossen* → nur per **QES** (§ 126a BGB). Rechtsprechung:
    **ArbG Gera 07.03.2024 – 2 Ca 936/23** (QES genügt, positiv),
    **ArbG Berlin 28.09.2021 – 36 Ca 15296/20** (QES-Voraussetzungen im
    Einzelfall verfehlt → Schriftform nicht gewahrt) (Belege:
    otto-schmidt.de Arbeitsrechts-Blog 21.04.2024).
  - **Kündigung/Aufhebungsvertrag:** § 623 BGB – elektronische Form
    **ausdrücklich ausgeschlossen** (juraforum 31.07.2026).
- **Fazit Regel:** einfache/fortgeschrittene Signatur oft *ausreichend
  anwendbar* (Beweislast des Unterzeichnenden, eIDAS Art. 25(1)), **QES
  = safe harbour** überall dort, wo Schriftform gilt (Befristung) – oder
  klassisch handschriftlich. Kein Szenario erzwingt „keine Wahl"; die Wahl
  ist **Euch überlassen**.

| Option | Rechtsgrad (eIDAS) | Kosten | Connector nötig? | Quelle |
|---|---|---|---|---|
| **A. Manuell (Papier + handschriftlich / gescanntes PDF)** | Handschrift = goldener Standard; Scan allein ≠ e-Signatur | 0 € | **Keiner** | § 126 BGB; eigene Prozess-Entscheidung (Design) |
| **B. DocuSeal (self-hosted, Open Source)** | SES („Legally-binding eSignature"); QES nur als Cloud-Pro-Add-on | **0 $** On-Prem Open-Source (`docuseal.com/pricing` „Open Source Free"); QES Cloud Pro: 2–4 $/QeS | Optional (externer Dienst, kein Projekt-Connector) | github.com/docusealco/docuseal (**AGPL-3.0** + Sec.7(b)); docuseal.com/pricing |
| **C. OpenSign (self-hosted)** | SES/einfache Signatur, Audit-Trail + Completion-Certificate | **0** (AGPL self-hosted; Cloud-Free-Plan „unlimited") | Optional | github.com/OpenSignLabs/OpenSign README: „licensed under the **AGPL-3**"; opensign.me Free-Plan |
| **D. eSign-API Free-Tier** (z.B. eSignature API by CraftMyPDF; eSign.com Basic) | SES (eIDAS) | **0 $**: 50 Dok./Monat bzw. Basic $0/5 Sign-Requests | Optional (API-Connector nötig, KEIN im Projekt) | esignature-api.com („Free plan: 50 documents"); esign.com/pricing |
| **E. Bundesdruckerei/D-Trust `sign-me` (QES-Fernsignatur)** | **QES** (= handschriftlich, eIDAS Art. 25(2)) | **Nicht öffentlich belegbar** – Preise nur nach Login (Direkt-/Umklappvertrag) | Optional (API vorhanden) | shop.marktplatz-deutschland-digital.de (Bundesdruckerei-Angebot); bundesdruckerei.de/vertrauensdienste. **KEIN Free-Tier öffentlich belegt.** |
| **F. e-Signature.eu API (Pay-as-you-go)** | QES/AES/**SES** wählbar | 0 € Abo; SES 0,4 Credit/Signatur, QES 4,95 €/Signatur (1 Credit) | Optional (API) | e-signature.eu/en/api-electronic-signature + Preisseite |

**Anzahl Signatur-Optionen in der Tabelle: 6 (A–F).**
Keine davon ist bisher eingebunden. **Entscheidung bleibt beim User – kein Code in dieser Phase.**

---

## 5. Lücke vs. ⚠️-Bipperz – was fehlt für „✅"

**Geschlossen am 24.09.2026 (USER-GO Code-Go):**

1. ✅ **Vertragsskelett** → `knowledge/templates/contract-templates/arbeitsvertrag-de-skeleton.md`
   (§ 2 NachwG 15 Punkte aus offiziellem Volltext, Formfall-Tabelle § 611a/§ 14/§ 623/§ 126a).
2. ✅ **Gehaltsfeld-Check „vor Vertrag"** → Runner-Task `contract_preflight` (HR-Klick,
   📞/Onboarding-Sektion): Stundenlohn vs. Mindestlohn aus Link-Katalog + Formfall-Hinweise.
3. ✅ **Recherche + Link-Katalog** → `ergebnisse/phase-d-p8-contract-recherche.md` +
   `knowledge/legal/contract-sources.md` (0 hartkodierte Links in Python).
4. ✅ **Skill** → `skills/contract-management/SKILL.md` (23.).

**Offen (bewusst NICHT in diesem GO):**

3. **Kein Signatur-Workflow / kein Signatur-Connector** (Option A–F, Abschnitt 4 – **User-Wahl steht**).
4. **Kein Vertrags-Status-Tracking-DB** – „Vertrag registriert" bleibt manuelles Häkchen
   (`onboarding-de.md:47`); Preflight-Report ersetzt das Häkchen nicht.
5. **Bipperz-Seite unklar:** für echtes „✅" bräuchte es zuerst eine
   User-Bestätigung, *dass* Punkt 8 (Vertragsmanagement) überhaupt ein
   Bipperz-Vergleichspunkt sein soll (0 Projektbelege, Abschnitt 1).

---

## 6. Verantwortlichkeiten

| Rolle | Verantwortung | Beleg / Regel |
|---|---|---|
| **Kandidat** | Vertrag prüfen, **unterschreiben** (handschriftlich/QES je nach Formfall), Identität bei QES-Fernsignatur bereitstellen (eID/VideoIdent/OTP); Erhalt ggf. bestätigen (NachwG-Textform) | § 126/126a BGB; § 14 Abs. 4 TzBfG; Abschnitt 4 |
| **HR (EMPLOYER)** | Vertrag **erstellen** (Vorlage), Gehalt gegen MiLoG/Blue-Card prüfen (`AGENTS.md:164-165`), Aushändigung/Nachweis nach NachwG, Formfall wählen (Schrift/Text/QES), „→ eingestellt" klicken → Onboarding-Release | `knowledge/legal/compliance-rules.md:37`, `knowledge/legal/visa-rules.md:158`, Variante A (Human-in-the-loop) |
| **Agent** | **Nur prüfen/vorschlagen:** Gehalt/Compliance-Reports liefern, Nachweise zusammentragen, Mails (Onboarding/Visum) senden. **Nie** selbst Vertrag erstellen, nie selbst signieren, nie selbst ein-/ablehnen | JA/NEIN-Gate + Variante A (`AGENTS.md`, agent-automation); **kein Code ohne User-Go** |

---

**STOPP aufgehoben für den Code-Go-Umfang oben.** Signatur (A–F) und Status-Tracking-DB bleiben
beim User; Preflight/Vorlage/Skill/Link-Katalog sind umgesetzt (Stand 24.09.2026).
