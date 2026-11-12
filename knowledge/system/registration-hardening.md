# Registrierungs-Härtung: E-Mail-Prüfung, Honeypot, Mindest-Füllzeit

**Stand:** 12.11.2026 · **Status:** implementiert (Phasen A + B) · **Code:**
`webui/registration_guard.py`, verdrahtet in `webui/pages/login.py`
· **Plan/Belege:** `ergebnisse/planung-5-7.md` (gitignored)

Normativ für die Registrierung über die WebUI. Login, Passwort-Reset und
Admin-Anmeldung sind **nicht** betroffen. Phasen C–E (IP-Limiter, Cloudflare,
Turnstile) sind hier bewusst nicht beschrieben — sie sind nicht implementiert.

## 1. Warum

Die Registrierung war die einzige offene Fläche ohne serverseitige Prüfung:

- Die E-Mail-Prüfung war **fünfmal** als Inline-Lambda kopiert und lief nur im
  Browser (`validation={…}`); der Handler hat sie nie erneut geprüft.
- Beide Registrierungs-Handler schreiben direkt per `conn.execute` in
  `candidates`/`employers` — es gibt keinen zentralen Ort, an dem eine Regel
  greifen könnte (Codemarken: `do_register`, `do_employer_register`).
- Registrierung und Login sind **keine HTTP-POSTs**, sondern Socket.IO-Frames
  über `/_nicegui_ws/socket.io`. Cloudflare/WAF sieht nur `GET /login` und den
  WS-Upgrade (101) — Prüfungen müssen deshalb in der App passieren.

## 2. Zwei Schichten, zwei Flags

| Flag | Default | Wirkung bei `0` |
|---|---|---|
| `KMHR_REGISTRATION_STRICT_EMAIL` | `1` | „log-only": eine abgelehnte Adresse wird geloggt, die Registrierung läuft weiter (Altverhalten) |
| `KMHR_REGISTRATION_HONEYPOT` | `1` | Honeypot **und** Mindest-Füllzeit sind aus (Altverhalten) |

Beide Flags werden **zur Laufzeit** gelesen (`registration_guard.strict_email_enabled`,
`honeypot_enabled`), nicht beim Import — ein Restart ist für das Umschalten
trotzdem nötig, weil die Seite im Prozess gebaut wird. Kein neues DB-Schema:
der Zustand ist der Render-Zeitpunkt der Seite (siehe §4).

Akzeptierte Off-Werte: `0`, `false`, `no`, `off` (Groß-/Kleinschreibung und
Leerraum egal). Alles andere — auch ein Tippfehler — lässt die Schicht **an**;
der Default ist der sichere Zustand.

## 3. Maßnahme 6 — E-Mail-Prüfung

`registration_guard.check_registration_email(raw) -> (ok, grund)` prüft in
dieser Reihenfolge:

| # | Regel | Grund-Code |
|---|---|---|
| 1 | nicht leer, genau ein `@` mit Inhalt davor/danach | `format` |
| 2 | Gesamtlänge ≤ 254 (RFC 5321) | `total_len` |
| 3 | Lokalteil ≤ 64 (RFC 5321) | `local_len` |
| 4 | Syntax nach `email-validator` (`check_deliverability=False`) | `format` |
| 5 | TLD in `RESERVED_TLDS` = `.invalid`, `.test`, `.localhost`, `.local`, `.example` | `reserved_tld` |
| 6 | TLD ≥ 2 Zeichen | `tld` |
| 7 | Domain nicht `example.com`/`example.net`/`example.org` | `reserved_domain` |

- **Zwei Verhalten, ein Ort:** `email_field_valid` ist die unveränderte
  Altregel (`"@" in v and "." in v`) für die drei Login-Felder (`email`,
  `e_email`, `a_email`); `registration_email_field_valid` ist die strikte
  Variante für `r_email`/`er_email`. Seed-/E2E-Konten tragen
  `@example.invalid` und müssen sich weiter **einloggen** können.
- **Server-seitig bindend:** `registration_email_blocked(raw)` läuft im Handler
  **vor** dem Hashen und vor dem INSERT. Die Client-Validierung ist nur UX; sie
  ist per DevTools umgehbar.
- **Kein DNS:** `check_deliverability=False`. Eine MX-Prüfung ist bewusst nicht
  Teil dieser Phase (Latenz, Resolver-Datenschutz, False Negatives).
- **Lücken, die `email-validator` offenlässt** (gemessen 12.11.2026):
  `anna@beispiel.c` und `anna@bücher.example` werden akzeptiert, 65 Zeichen im
  Lokalteil ebenfalls. Genau diese Fälle fangen die Regeln 3, 5 und 6.
- **Neue Abhängigkeit:** `email-validator==2.3.0` in `requirements.txt`.
  Vorher nur transitiv vorhanden, jetzt direkt importiert (zieht `dnspython`
  und `idna`). Alternative wäre eine Regex gewesen — die kann IDN/EAI nicht
  sauber abbilden und wäre bei jeder Verschärfung Handarbeit.

### Meldung

`Bitte eine gueltige E-Mail eingeben.` — derselbe Katalog-Key wie beim
Passwort-Reset (kein neuer i18n-Eintrag). Der Grund-Code geht **nie** an die
UI; er steht nur im Server-Log, ohne Adresse (DSGVO).

## 4. Maßnahme 5a — Honeypot + Mindest-Füllzeit

- **Lockfeld:** je Registrierungs-Panel ein `ui.input`, per
  `_honeypot_field(marker)` **off-screen** positioniert
  (`position:absolute; left:-10000px; …`), `tabindex=-1`, `aria-hidden=true`,
  `autocomplete=off`. Off-screen statt `display:none`, weil viele Bots
  `display:none`-Felder überspringen.
- **Startzeit:** `time.monotonic()` beim Rendern des Panels (nicht im Handler).
- **Schwelle:** `MIN_FILL_SECONDS = 3.0`. Absenden unter 3 Sekunden nach dem
  Rendern gilt als Bot-Signal.
- **Entscheidung:** `registration_blocked(honeypot_wert, elapsed)` prüft erst
  das Lockfeld, dann die Zeit — eine Funktion, eine Regel.
- **Eine Meldung für beide Gründe:**
  `Registrierung derzeit nicht möglich. Bitte versuchen Sie es später erneut.`
  (DE/EN/FR/AR im Katalog). Kein Hinweis auf Honeypot oder Timing: sonst kann
  der Bot die Erkennung kalibrieren. Der Grund steht nur im Log, ohne Eingabe.

### Bekannte Grenzen

- Ein gezielter Bot umgeht beides (er liest das DOM und wartet). Die Schicht
  stoppt naive Form-Bots, nicht einen Angreifer mit Browser.
- Sehr schnelle Menschen (Autofill, Passwortmanager) können unter 3 Sekunden
  liegen und die generische Meldung sehen. Deshalb ist die Schwelle konservativ
  und die Schicht per Flag abschaltbar; ein zweiter Versuch mit kurzer Pause
  gelingt.
- Nur ein Prozess: `ui.run(...)` läuft ohne `workers`, der Zustand ist pro
  Seiten-Render lokal. Kein Redis, kein In-Memory-Zähler über Requests hinweg.

## 5. Verhältnis zu Consent (unverändert)

Honeypot, Timing und E-Mail-Prüfung sind **keine** Einwilligung und ersetzen
weder die AGB-/Datenschutz-Checkbox (`_consent_checkbox`) noch den Nachweis in
`consents`. `db.CONSENT_VERSION` bleibt `2026-10-26`; die Reihenfolge
Consent-Guard → INSERT → `db.complete_registration` ist unverändert
(`tests/test_consent_ui.py`).

## 6. Nachweise

| Test | Prüft |
|---|---|
| `tests/test_registration_guard.py` | Validator (gültig/ungültig, IDN, Plus-Adressen, Umlaute, Längen, Reserve-TLDs/-Domains), Flags, Honeypot, Timing-Grenze, log-only |
| `tests/test_registration_ui.py` | Rendering der echten `/login`-Seite: Lockfeld off-screen/`tabindex`/`aria-hidden`, gefüllter Honeypot → generische Meldung ohne DB-Zeile, zu schnelles Absenden, serverseitiger Reserve-Domain-Guard, **Flag 0 = Altverhalten** (inkl. erfolgreicher Registrierung) |
| `tests/test_registration_wiring.py` | keine fünfte Kopie der Altregel, 3× tolerant / 2× strikt, Guards vor dem INSERT, i18n in allen vier Katalogen |
| `tests/e2e_notifications_flow.py` | Registrierung durch die echte UI (E2E, isolierte Instanz); wartet ~3,7 s und liegt damit über der Schwelle |

**Testkonten:** Die strikte Regel lehnt `@example.invalid` ab. Der
E2E-Registrierungsflow nutzt deshalb `r35-e2e-<TS>@e2e.hanibal-ai.com`; die
Login-Konten in `tests/e2e_harness.py` bleiben unverändert
(`@example.invalid`, toleranter Login).

## 7. Design-Entscheidungen (keine externe Norm)

- **Asymmetrie Login/Registrierung:** Reservierte Adressen sind zum Login
  erlaubt, zur Registrierung nicht. Grund: Bestandskonten (Seed, E2E) dürfen
  nicht ausgesperrt werden; neue Konten auf reservierten Domains sind wertlos
  (keine Zustellung).
- **`example.com` gesperrt, obwohl die IANA-Testdomäne:** Der Auftrag vom
  12.11.2026 nennt `example.com` ausdrücklich als abzulehnende Reserve-Domain.
  Die Test-Suite nutzt deshalb eine Subdomain der Betreiber-Domain. Soll
  `example.com` für Tests erlaubt werden, ist das eine Ein-Zeilen-Änderung in
  `RESERVED_DOMAINS` — dann muss die E2E-Adresse zurückgestellt werden.
- **3 Sekunden statt 2:** bewusst konservativ gewählt (Auftrag: „~3 s") und
  gegen die E2E-Wartezeit geprüft.
- **Generische Meldung statt „zu schnell":** verhindert Bot-Feedback; der Preis
  ist eine unpräzise Meldung für sehr schnelle Menschen.
