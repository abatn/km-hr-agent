# Contract-Management-Recherche: Link-Katalog (Single Source of Truth)

> **Stand:** 24.09.2026 (Recherche via MCP `fetch` + lokale Playwright-Session; FR-Volltexte via ansvar `get_provision`, siehe `ergebnisse/phase-d-p8-contract-recherche.md`)
> **Regel (USER-GO):** **Keine hartkodierten Links in Python.** Code liest dieses MD und extrahiert die URLs
> per Markdown-Link-Pattern zur Laufzeit. Bei Widerspruch: diese Datei gewinnt (Lab-Prinzip 3 → MD ist Quelle).
> **Pflege:** URLs nur hier ändern; jede Änderung mit Abrufdatum + Status (✅/⚠️/❌) versehen.

## A. Offizielle Rechtsquellen (DE/EU)

| Key | Quelle | URL | Abruf 24.09.2026 | Status |
|---|---|---|---|---|
| `bgb_126a` | § 126a BGB (elektronische Form → QES) | [gesetze-im-internet.de/bgb/__126a.html](https://www.gesetze-im-internet.de/bgb/__126a.html) | ✅ Volltext | aktuell |
| `bgb_623` | § 623 BGB (Kündigung: Schriftform, e-Form ausgeschlossen) | [gesetze-im-internet.de/bgb/__623.html](https://www.gesetze-im-internet.de/bgb/__623.html) | ✅ Volltext | aktuell |
| `bgb_611a` | § 611a BGB (Arbeitsvertrag, formfrei) | [gesetze-im-internet.de/bgb/__611a.html](https://www.gesetze-im-internet.de/bgb/__611a.html) | ✅ Volltext | aktuell |
| `nachwg_2` | § 2 NachwG (Textform seit 2025 + 15 Pflichtangaben) | [gesetze-im-internet.de/nachwg/__2.html](https://www.gesetze-im-internet.de/nachwg/__2.html) | ✅ Volltext | aktuell |
| `milog_1` | § 1 MiLoG (Wert via Rechtsverordnung, nicht im Gesetz) | [gesetze-im-internet.de/milog/__1.html](https://www.gesetze-im-internet.de/milog/__1.html) | ✅ Volltext | aktuell (Wert dort alt: 12 €) |
| `tzbg_14` | § 14 TzBfG (Befristung: Schriftform Abs. 4) | [buzer.de/14_TzBfG.htm](https://www.buzer.de/14_TzBfG.htm) | ✅ Volltext | aktuell (Datenbank-Spiegel) |
| `eidas_2014` | eIDAS-VO (EU) 910/2014 Art. 25 (SES/AES/QES) | [eur-lex.europa.eu/eli/reg/2014/910/oj](https://eur-lex.europa.eu/eli/reg/2014/910/oj) | ❌ via fetch nicht darstellbar | Spezifikationsbeleg (Spec §4), Volltext prüfen |
| `eidas_2024` | VO (EU) 2024/1183 (eIDAS 2.0 / Wallet) | [eur-lex.europa.eu/eli/reg/2024/1183/oj](https://eur-lex.europa.eu/eli/reg/2024/1183/oj) | ❌ via fetch nicht darstellbar | Kontextquelle |
| `mindestlohn_2026` | Mindestlohn 13,90 €/h seit 01.01.2026 (**Primär belegt seit 25.09.2026, P6**) | MiLoV5 § 1, **BGBl. 2025 I Nr. 268 v. 07.11.2025**, in Kraft 01.01.2026 (MiLoG § 1 Abs. 2 = Ermächtigung, BMAS) — sekundär: [en.wikipedia.org/wiki/Minimum_wage_in_Germany](https://en.wikipedia.org/wiki/Minimum_wage_in_Germany) | ✅ (Primär, Abruf 25.09.2026) | ~~⚠️ Primärquelle offen – 404/403 am 24.09.2026~~ geschlossen 25.09.2026 (Quelle: recherche-plan-restpunkte-2026-09-25.md:231-242) |

## A2. Frankreich (Code du travail + Service-Public, Abruf 24.09.2026)

> **Tool-Hinweis:** Legifrance-HTML liefert 403/robots (auch via Playwright Bot-Wall).
> Normtexte der 7 Artikel unten via MCP `ansvar-german-law` / Gateway-Tool `get_provision`
> (`canonical_ref` `code-travail:artL…`, `last_verified` 2026-09-24, Lizenz DILA/Legifrance Étalab-2.0).
> `source_url` = Legifrance-Code-Übersicht (Volltext-Proxy, kein eigener Deep-Link).

| Key | Quelle | URL | Abruf 24.09.2026 | Status |
|---|---|---|---|---|
| `fr_code_travail` | Code du travail (LEGITEXT000006072050) – Überblick/Permalink | [legifrance.gouv.fr/codes/texte_lc/LEGITEXT000006072050](https://www.legifrance.gouv.fr/codes/texte_lc/LEGITEXT000006072050/) | ⚠️ Direkt 403; Volltext via ansvar `get_provision` | aktuell (Proxy 24.09.2026) |
| `fr_l1221_1` | Art. L1221-1 – Formfreiheit des contrat de travail | [legifrance … L1221-1](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006902514/) | ⚠️ ansvar-Proxy ✅ | aktuell |
| `fr_l1221_6` | Art. L1221-6 – Bewerberdaten nur für Stellenbesetzung | [legifrance … L1221-6](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006902520/) | ⚠️ ansvar-Proxy ✅ | aktuell |
| `fr_l1221_7` | Art. L1221-7 – Schutz personenbezogener Bewerberdaten | [legifrance … L1221-7](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006902521/) | ⚠️ ansvar-Proxy ✅ | aktuell |
| `fr_l1221_8` | Art. L1221-8 – Hinweis auf digitale Rekrutierungsmethoden | [legifrance … L1221-8](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006902522/) | ⚠️ ansvar-Proxy ✅ | aktuell |
| `fr_l1242_12` | Art. L1242-12 – CDD schriftlich + präziser Motivgrund | [legifrance … L1242-12](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006903584/) | ⚠️ ansvar-Proxy ✅ | aktuell |
| `fr_l1243_8` | Art. L1243-8 – CDD-Verlängerungs-/Folge-Regeln | [legifrance … L1243-8](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006903637/) | ⚠️ ansvar-Proxy ✅ | aktuell |
| `fr_l1243_11` | Art. L1243-11 – Fortsetzung nach CDD-Ende → CDI de plein droit | [legifrance … L1243-11](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006903640/) | ⚠️ ansvar-Proxy ✅ | aktuell |
| `fr_smic` | SMIC brut horaire **12,31 €** (Vérifié 01.06.2026) | [service-public.fr/particuliers/vosdroits/F2300](https://www.service-public.fr/particuliers/vosdroits/F2300) | ✅ HTML 200 + Tabellenwert | aktuell |
| `fr_duree_travail` | Dauer du travail: 35 h/Woche, max 48 h/Woche, Ø 44 h (12 Wochen) | [service-public.fr/particuliers/vosdroits/F1911](https://www.service-public.fr/particuliers/vosdroits/F1911) | ✅ HTML 200 | aktuell (Vérifié 25.09.2025) |
| `fr_licenciement` | Licenciement pour motif personnel (Definition) | [service-public.fr/particuliers/vosdroits/F2835](https://www.service-public.fr/particuliers/vosdroits/F2835) | ✅ HTML 200 | aktuell |
| `fr_cddi` | CDD d'insertion (CDDI) | [service-public.fr/particuliers/vosdroits/F14100](https://www.service-public.fr/particuliers/vosdroits/F14100) | ✅ HTML 200 | aktuell |
| `fr_cdii` | CDI intermittent (CDII) – Pflichtangaben | [service-public.fr/particuliers/vosdroits/F2247](https://www.service-public.fr/particuliers/vosdroits/F2247) | ✅ HTML 200 | aktuell |

## A3. Schweiz (Obligationenrecht OR, Fedlex, Abruf 24.09.2026 via Playwright)

> **Tool-Hinweis:** Fedlex-HTML-ELI-Seiten sind JS-Shells (fetch unbrauchbar).
> Volltext via lokale Playwright-Session (`ch_or_319.txt`, ~1.03 Mio. Zeichen) + PDF-A-Speicher (`/tmp/or-27.pdf`, 554 S.).

| Key | Quelle | URL | Abruf 24.09.2026 | Status |
|---|---|---|---|---|
| `ch_or_titel10` | OR Titel 10 Arbeitsvertrag – HTML-Übersicht (Art. 319–337f) | [fedlex.admin.ch/eli/cc/27/317_321_377/de](https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de) | ✅ Playwright-Volltext | aktuell (Fassung 01.01.2024) |
| `ch_or_pdf` | OR PDF-A (Arbeitsvertrag) – amtliche Fassung 01.01.2024 | [fedlex …/eli-cc-27-317_321_377-20240101-de-pdf-a.pdf](https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/27/317_321_377/20240101/de/pdf-a/eli-cc-27-317_321_377-20240101-de-pdf-a.pdf) | ✅ Download 4.7 MB / 554 S. | aktuell |
| `ch_or_319` | Art. 319 – Einzelarbeitsvertrag (Definition, auch Teilzeit) | [fedlex … Titel 10 HTML](https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de) | ✅ Volltext-Extrakt | aktuell |
| `ch_or_320` | Art. 320 – Formfreiheit (keine besondere Form, soweit Gesetz nichts anderes bestimmt) | [fedlex … Titel 10 HTML](https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de) | ✅ Volltext-Extrakt | aktuell |
| `ch_or_328` | Art. 328 – Persönlichkeitsschutz / Arbeitsschutz des Arbeitgebers | [fedlex … Titel 10 HTML](https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de) | ✅ Volltext-Extrakt | aktuell |
| `ch_or_330b` | Art. 330b – Schriftl. Informationspflicht (5 Pflichtangaben, 1 Monat) | [fedlex … Titel 10 HTML](https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de) | ✅ Volltext-Extrakt | aktuell |

**Korrektur (24.09.2026):** Art. **319a / 319b OR existieren NICHT** (vorherige Annahme verworfen).
Die Informationspflicht steht in **Art. 330b** (Abs. 1 lit. a–e: Namen, Beginn, Funktion, Lohn/Zuschläge, Wochenarbeitszeit).

## B. Wissenschaft (aktuell)

| Key | Quelle | URL/DOI | Status |
|---|---|---|---|
| `cuad_paper` | CUAD: Expert-Annotated NLP Dataset for Legal Contract Review (Hendrycks et al., NeurIPS 2021, 98 Zitate) | [arxiv.org/abs/2103.06268](https://arxiv.org/abs/2103.06268) | ✅ abstract + OpenAlex Metadaten |
| `empfl_llm_2025` | Automated Employment Law Case Analysis Using LLMs (Gryspeerdt 2025) | [doi.org/10.24908/iqurcp19921](https://doi.org/10.24908/iqurcp19921) | ✅ CrossRef |
| `cuad_scan_2026` | Document AI robustness on CUAD scans (Ferozabadkar/Deshpande 2026) | [doi.org/10.2139/ssrn.7500462](https://doi.org/10.2139/ssrn.7500462) | ✅ CrossRef |
| `gpts_labor` | GPTs are GPTs (Eloundou et al. 2023, 550 Zitate) | [arxiv.org/abs/2303.10130](https://arxiv.org/abs/2303.10130) | ✅ OpenAlex |
| `clause_qa_kd_2025` | Efficient legal contract clause extraction using QA-based knowledge distillation (WWW 28(6), 2025) | [doi.org/10.1007/s11280-025-01375-7](https://doi.org/10.1007/s11280-025-01375-7) | ✅ CrossRef 24.09.2026 |
| `llm_law_survey_2025` | Exploring LLMs Applications in Law (IEEE Access 13:18253–18276, 106 Zitate) | [doi.org/10.1109/ACCESS.2025.3533217](https://doi.org/10.1109/ACCESS.2025.3533217) | ✅ CrossRef 24.09.2026 |
| `hohfeld_ontology_2026` | From Clause Types to Remedial Grammar: A Two-Axis Hohfeldian Ontology for LLM-Assisted Contract Review (Kao 2026, SSRN/CrossRef) | [doi.org/10.2139/ssrn.7236280](https://doi.org/10.2139/ssrn.7236280) | ✅ CrossRef 24.09.2026 (preprint) |

## C. GitHub (Stand 24.09.2026, GitHub REST API)

| Key | Repo | URL | Metadaten (API) | Lizenz |
|---|---|---|---|---|
| `docuseal` | Open-Source-DocuSign-Alternative | [github.com/docusealco/docuseal](https://github.com/docusealco/docuseal) | 18.611 ⭐, Push 2026-09-21 | AGPL-3.0 |
| `opensign` | Free/Open-Source DocuSign-Alternative | [github.com/OpenSignLabs/OpenSign](https://github.com/OpenSignLabs/OpenSign) | 7.030 ⭐, Push 2026-08-21 | AGPL-3 (README) |
| `claude_legal_skill` | Contract-Review-Skill (CUAD-Risk-Detection) – Vorbild | [github.com/evolsb/claude-legal-skill](https://github.com/evolsb/claude-legal-skill) | 452 ⭐, Push 2026-07-23 (API 24.09.2026) | MIT |
| `cuad_repo` | CUAD-Dataset (NeurIPS 2021) | [github.com/The-Atticus-Project/cuad](https://github.com/The-Atticus-Project/cuad) | 559 ⭐ | – |

## D. Verwendungsregel für Code

```text
knowledge/legal/contract-sources.md  →  Python liest MD  →  regex \[[^\]]+\]\((https?://[^)]+)\)
Kein "https://"-Literal in *.py (Ausnahme: connectors-/MCP-Server-Konfiguration in opencode.json).
Runner contract_preflight liest derzeit die DE-Keys (Abschnitt A); FR/CH-Keys (A2/A3) liegen bereit
für erweiterte Länder-Prüfung ohne Code-Hartkodierung.
```
